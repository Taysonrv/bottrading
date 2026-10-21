"""Public-data forward test of one shared PAPER wallet, separate from ema20.

Run explicitly; no live adapter, API key, automatic renewal or wallet migration.
"""
import argparse
from decimal import Decimal as D
import json
from pathlib import Path
import time
from .data import PublicBinance, retry
from .main import single_runner, save, normalized_rules, parse_book
from .portfolio import Portfolio, SYMBOLS
from .scanner import scan
from .selection import preview, choose

ROOT=Path(__file__).resolve().parent.parent


class Session:
    def __init__(self,root,client):
        self.root=Path(root);self.client=client;self.broker=Portfolio(root)
        self.folder=self.broker.path.parent;self.last_scan=0;self.report={};self.last_bid=None

    def book(self,symbol):
        rules=normalized_rules(retry(lambda:self.client.fetch_symbol_info(symbol)),symbol,int(retry(self.client.fetch_time)))
        before=time.monotonic();raw=retry(lambda:self.client.fetch_book(symbol))
        now=int(retry(self.client.fetch_time))
        if time.monotonic()-before>3:raise ValueError('SLOW_BOOK')
        return rules,parse_book(raw,symbol),now

    def cycle(self,plan):
        now=int(retry(self.client.fetch_time))
        if now-self.last_scan>=60000:
            self.report=scan(self.client,now,'15m');self.last_scan=now
            save(self.folder/'radar.json',self.report)
        s=self.broker.snapshot();holding=s['position'] or s['pending'];reason='WAITING_SIGNAL'
        if holding:
            symbol=holding['symbol'];rules,(bid,ask,bq,aq),now=self.book(symbol)
            self.last_bid=bid
            exit_signal=any(row.get('symbol')==symbol and row.get('status')=='OK' and row.get('action')=='EXIT_LONG' and
                            type(row.get('candle_close_ms')) is int and 0<=now-row['candle_close_ms']<=120000 for row in self.report.get('pairs',[]))
            reason=self.broker.quote('q_'+symbol.replace('/','')+'_'+str(now),rules,bid,ask,(aq if s['pending'] else bq)*D('.1'),now,now,exit_signal)
        else:
            candidates=[];books={}
            for row in self.report.get('pairs',[]):
                symbol=row.get('symbol');close=row.get('candle_close_ms')
                if symbol not in SYMBOLS or row.get('action')!='ENTER_LONG' or type(close) is not int or close<=plan['start_bar']:continue
                key='entry_'+symbol.replace('/','')+'_'+str(close)
                if key in s['orders']:continue
                rules,(bid,ask,bq,aq),actual=self.book(symbol)
                candidate=preview(row,rules,bid,ask,now_ms=actual,quote_ms=actual,cash=D(s['cash']),stopped=bool(s['halt']) or self.broker.stopped())
                candidates.append(candidate);books[symbol]=(key,row,rules,bid,ask,actual)
            selected=choose(candidates)
            if selected:
                key,row,rules,bid,ask,actual=books[selected]
                # Re-read the chosen book immediately before the transactional
                # reservation; another symbol never receives independent cash.
                rules,(bid,ask,_,_),actual=self.book(selected)
                reason=self.broker.reserve(key,row,rules,bid,ask,actual,actual)['reason'];self.last_bid=bid
        return self.publish('RUNNING',reason,plan)

    def publish(self,phase,reason,plan):
        s=self.broker.snapshot();now=int(time.time()*1000)
        # A balance without a recent mark remains unknown, not flat equity.
        pos=s['position'];equity=None
        if not pos:equity=s['cash']
        elif self.last_bid is not None:equity=str(D(s['cash'])+D(pos['quantity'])*self.last_bid*D('.999')*D('.999'))
        report=dict(mode='PAPER',phase=phase,reason=reason,updated_ms=now,end_ms=plan['end_ms'],
                    symbols=list(SYMBOLS),timeframe='15m',initial_capital='20',cash=s['cash'],equity=equity,
                    position=pos,pending=s['pending'],fees=s['fees'],realized=s['realized'],halt=s['halt'],
                    orders=list(s['orders'].values())[-100:],fills=s['fills'][-100:],real_orders=0,
                    note='Independent shared-wallet experiment; do not sum with EMA. Synthetic stops require a running process.')
        save(self.folder/'status.json',report)
        return report


def main():
    parser=argparse.ArgumentParser(description='Six-pair shared wallet, PUBLIC data, PAPER only. New independent experiment: total 20 USDT.')
    parser.add_argument('--data-dir',type=Path,default=ROOT)
    parser.add_argument('--start',action='store_true')
    args=parser.parse_args();session=Session(args.data_dir.resolve(),None)
    if not args.start:
        print('Not started. --start explicitly starts a separate 20-USDT PAPER experiment; existing EMA balances are not imported.')
        return
    with single_runner(session.folder/'runner.lock'):
        if session.broker.stopped():raise SystemExit('STOP active; not removed.')
        session.client=PublicBinance();now=int(retry(session.client.fetch_time))
        plan_path=session.folder/'plan.json'
        if plan_path.exists():
            plan=json.loads(plan_path.read_text(encoding='utf-8'))
            if type(plan.get('end_ms')) is not int or now>=plan['end_ms']:raise SystemExit('Session expired; no deadline or cash reset.')
            session.broker.snapshot()
        else:
            if session.broker.path.exists():raise SystemExit('Ledger without plan; preserve for review.')
            session.broker.initialize(now)
            plan=dict(start_ms=now,end_ms=now+86400000,start_bar=now//900000*900000)
            save(plan_path,plan)
        failures=0;reason='FAILURE'
        try:
            while True:
                if session.broker.stopped():reason='STOP';break
                if int(time.time()*1000)>=plan['end_ms']:reason='DEADLINE';break
                try:
                    report=session.cycle(plan);failures=0
                    print(json.dumps({k:report[k] for k in ('mode','phase','reason','cash','equity','halt')},ensure_ascii=True),flush=True)
                    if report['halt'] and not report['position']:reason=report['halt'];break
                except Exception:
                    failures+=1;session.last_bid=None
                    session.publish('DEGRADED','PUBLIC_DATA_OR_LEDGER_ERROR',plan)
                    if failures>=5:reason='FAILURE_LIMIT';break
                time.sleep(15)
        except KeyboardInterrupt:reason='INTERRUPTED'
        finally:
            session.broker.cancel_pending(reason)
            session.publish('STOPPED',reason,plan)
            print('Stopped; inventory preserved, pending entry canceled. No real orders.',flush=True)


if __name__=='__main__':main()
