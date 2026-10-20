"""Bounded forward PAPER session with public REST prices; no real broker."""
from contextlib import contextmanager
from dataclasses import asdict, replace
from decimal import Decimal as D, InvalidOperation
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time
from .config import load_settings, ConfigError
from .data import PublicBinance, DataError, TransientDataError, download, retry, STEPS, milliseconds
from .strategy import EmaAtrStrategy, StrategyError
from .risk import Rules, RiskError, amount, decimal_policy
from .execution import PaperBroker, ExecutionError, floor

ROOT=Path(__file__).resolve().parent.parent


def save(path,value):
    temporary=path.with_suffix('.tmp')
    with temporary.open('w',encoding='utf-8') as output:
        json.dump(value,output,ensure_ascii=False,indent=2,default=str,allow_nan=False);output.flush();os.fsync(output.fileno())
    temporary.replace(path)


@contextmanager
def single_runner(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0,2)
        if not handle.tell():handle.write(b'0');handle.flush()
        handle.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:raise ExecutionError('Esta sessão já possui um iniciador ativo.') from None
        try:yield
        finally:
            handle.seek(0)
            if os.name=='nt':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


def normalized_rules(info,symbol,now_ms):
    """Only normalized LIMIT constraints for PAPER; not a full live-order validator."""
    try:
        if info['symbol']!=symbol.replace('/','') or info['status']!='TRADING' or info.get('isSpotTradingAllowed') is not True:raise ValueError
        filters={row['filterType']:row for row in info['filters']}
        price=filters['PRICE_FILTER'];lot=filters['LOT_SIZE']
        notionals=[filters[k] for k in ('MIN_NOTIONAL','NOTIONAL') if k in filters]
        if not notionals:raise ValueError
        lower=max(D(n['minNotional']) for n in notionals)
        upper=min([D(n['maxNotional']) for n in notionals if 'maxNotional' in n]+[D('1e20')])
        return Rules(symbol,now_ms,D(lot['stepSize']),D(lot['minQty']),D(lot['maxQty']),D(price['tickSize']),
                     D(price['minPrice']),D(price['maxPrice']) or D('1e20'),lower,upper)
    except (KeyError,TypeError,ValueError,InvalidOperation):raise DataError('Filtros Spot insuficientes ou inválidos.') from None


def parse_book(raw,symbol):
    try:
        if raw['symbol']!=symbol.replace('/',''):raise ValueError
        if any(not isinstance(raw.get(k),str) or len(raw[k])>64 for k in ('bidPrice','askPrice','bidQty','askQty')):raise ValueError
        values=tuple(D(raw[k]) for k in ('bidPrice','askPrice','bidQty','askQty'))
        for i,value in enumerate(values):amount(value,positive=i<2)
        if values[0]>values[1]:raise ValueError
        return values
    except (KeyError,TypeError,ValueError,InvalidOperation):raise DataError('Livro público inválido.') from None


class PaperSession:
    """Replay indicators causally, trade only new closes, and preserve wallet on exit."""
    def __init__(self,root,cfg,client,*,hours=24,clock=time.time):
        self.root=Path(root);self.cfg=cfg;self.client=client;self.clock=clock;self.step=STEPS[cfg.timeframe]
        self.broker=PaperBroker(root,cfg,control_root=ROOT)
        if self.broker.risk._stopped():raise ExecutionError('STOP acionado; nenhuma sessão iniciada.')
        self.path=self.root/'session.json';self.status_path=self.root/'status.json'
        self.identity=hashlib.sha256(json.dumps({'config':asdict(cfg),'sources':{name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ('config.py','data.py','strategy.py','risk.py','execution.py','main.py')}},sort_keys=True,default=str).encode()).hexdigest()
        now=milliseconds(retry(client.fetch_time));self.offset=now-int(clock()*1000)
        if self.path.exists():
            plan=json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(plan,dict) or plan.get('identity')!=self.identity:raise ExecutionError('Sessão pertence a outro código/configuração; não reiniciada.')
            if plan['end_ms']<=now:raise ExecutionError('Prazo da sessão encerrado; preserve e revise o resultado.')
            for key in ('started_ms','end_ms','warmup_start','last_decision_bar'):milliseconds(plan[key])
            if not plan['warmup_start']<plan['started_ms']<plan['end_ms'] or plan['last_decision_bar']%self.step:raise ExecutionError('Plano de sessão inválido.')
            self.broker.snapshot()
        else:
            end=now//self.step*self.step
            plan=dict(identity=self.identity,started_ms=now,end_ms=now+int(hours*3600000),warmup_start=end-EmaAtrStrategy(cfg).warmup_bars*self.step,
                      last_decision_bar=end-self.step)
            self.root.mkdir(parents=True,exist_ok=True)
            # Preserve intent BEFORE initialization; incomplete startup fails closed.
            with self.path.open('x',encoding='utf-8') as output:json.dump(plan,output)
            self.broker.initialize(now)
        self.plan=plan;self.strategy=EmaAtrStrategy(cfg)
        self.candle_end=now//self.step*self.step
        history=download(client,cfg.symbol,cfg.timeframe,plan['warmup_start'],self.candle_end)
        for c in history.candles:self.strategy.update(c,as_of_ms=c.open_ms+self.step)
        # No trades from old bars after a restart/offline interval.
        if plan['last_decision_bar']<self.candle_end-self.step:
            plan['last_decision_bar']=self.candle_end-self.step;save(self.path,plan)
        self.rules=None;self.last_signal='WARMUP_REPLAYED';self.last_bid=None;self.price_received_ms=None;self.pending_signal=None

    def now(self):return int(self.clock()*1000)+self.offset

    @decimal_policy
    def cycle(self):
        if self.broker.risk._stopped():return self.stop('STOP')
        observed=milliseconds(retry(self.client.fetch_time));self.offset=observed-int(self.clock()*1000)
        if observed>=self.plan['end_ms']:return self.stop('DEADLINE')
        end=observed//self.step*self.step
        latest=None
        if end>self.candle_end:
            history=download(self.client,self.cfg.symbol,self.cfg.timeframe,self.candle_end,end)
            for c in history.candles:latest=self.strategy.update(c,as_of_ms=c.open_ms+self.step)
            self.candle_end=end;self.pending_signal=latest
        latest=self.pending_signal
        if self.rules is None or observed-self.rules.observed_ms>1800000:
            self.rules=normalized_rules(retry(lambda:self.client.fetch_symbol_info(self.cfg.symbol)),self.cfg.symbol,self.now())
        before=int(self.clock()*1000)
        raw=retry(lambda:self.client.fetch_book(self.cfg.symbol))
        after=int(self.clock()*1000)
        if after-before>3000:raise TransientDataError('Livro recebido com latência excessiva.')
        bid,ask,bid_qty,ask_qty=parse_book(raw,self.cfg.symbol);self.last_bid=bid
        now=self.now();quote_ms=now;self.price_received_ms=quote_ms
        s=self.broker.snapshot();active=s['orders'].get(s['active'])
        canceled=False
        if active and active['side']=='BUY' and (now-active['created_ms']>60000 or (latest is not None and latest.action=='EXIT_LONG')):
            self.broker.cancel(s['active'],now);s=self.broker.snapshot();active=None;canceled=True
        # Conservative hypothesis: at most 10% of the displayed side per sample.
        liquidity=(ask_qty if active and active['side']=='BUY' else bid_qty)*D('.1')
        result=self.broker.process_quote('q_'+str(quote_ms),bid=bid,ask=ask,available_quantity=liquidity,quote_ms=quote_ms,now_ms=now,rules=self.rules)
        if canceled:result['reason']='ENTRY_CANCELED_STALE_OR_EXIT_SIGNAL'
        s=self.broker.snapshot()
        if latest is not None and latest.candle_open_ms>self.plan['last_decision_bar']:
            self.last_signal=latest.action+':'+latest.reason
            intent=('entry_' if latest.action=='ENTER_LONG' else 'exit_')+str(latest.candle_open_ms)
            # Deterministic ID prevents resubmission after a response/checkpoint loss.
            if intent not in s['orders']:
                if latest.action=='ENTER_LONG' and now-(latest.candle_open_ms+self.step)<=120000:
                    order=self.broker.submit_entry(intent,bid=bid,ask=ask,quote_ms=quote_ms,now_ms=self.now(),rules=self.rules);result['reason']=order['reason']
                elif latest.action=='ENTER_LONG':result['reason']='STALE_SIGNAL'
                elif latest.action=='EXIT_LONG' and D(s['units'])>0 and not (s['active'] and s['orders'][s['active']]['side']=='SELL'):
                    order=self.broker.submit_exit(intent,bid=bid,ask=ask,quote_ms=quote_ms,now_ms=self.now(),rules=self.rules);result['reason']=order['reason']
            self.plan['last_decision_bar']=latest.candle_open_ms;save(self.path,self.plan);self.pending_signal=None
        return self.report('RUNNING',result['reason'])

    @decimal_policy
    def report(self,phase,reason):
        s=self.broker.snapshot();cash=D(s['cash']);units=D(s['units']);cost=D(s['cost'])
        marked=units*floor(self.last_bid*(1-self.cfg.slippage_rate),self.rules.price_tick)*(1-self.cfg.fee_rate) if self.last_bid is not None and self.rules is not None else None
        equity=cash+marked if marked is not None else cash if units==0 else None
        active=s['orders'].get(s['active'])
        report=dict(mode='PAPER',phase=phase,reason=reason,updated_ms=self.now(),end_ms=self.plan['end_ms'],symbol=self.cfg.symbol,
                    capital=str(self.cfg.capital),max_order_budget=str(self.cfg.max_order_notional),
                    equity=str(equity) if equity is not None else None,pnl=str(equity-self.cfg.capital) if equity is not None else None,
                    price_received_ms=self.price_received_ms,price_age_ms=self.now()-self.price_received_ms if self.price_received_ms is not None else None,
                    cash=s['cash'],reserved=s['reserved'],units=s['units'],realized=s['realized'],fees=s['fees'],protection=s['protection'],
                    last_signal=self.last_signal,buy_fills=sum(f['side']=='BUY' for f in s['fills']),sell_fills=sum(f['side']=='SELL' for f in s['fills']),
                    active_order=active,risk_events=self.broker.risk.events(),approved=False,real_orders=0,
                    price_source='Binance public REST bookTicker; timestamp local de recebimento, sem idade do livro na origem.',
                    fill_model='10% do tamanho exibido por amostra é hipótese; amostras podem reutilizar liquidez. Não reproduz fila.')
        save(self.status_path,report)
        print(json.dumps({k:report[k] for k in ('mode','phase','reason','equity','pnl','units','buy_fills','sell_fills','last_signal')},ensure_ascii=False),flush=True)
        return report

    def stop(self,reason):
        s=self.broker.snapshot()
        if s['active']:self.broker.cancel(s['active'],max(self.now(),s['last_ms']))
        return self.report('STOPPED',reason)


def main():
    parser=argparse.ArgumentParser(description='Sessão contínua PAPER, dados públicos, sem chaves ou ordens reais.')
    parser.add_argument('mode',choices=['paper'])
    parser.add_argument('--session',default='ema20')
    parser.add_argument('--hours',type=int,default=24)
    parser.add_argument('--order-budget',type=D,help='Teto fictício por ordem incluindo taxa; mantém risco máximo de 1%')
    parser.add_argument('--poll-seconds',type=int,default=15)
    parser.add_argument('--once',action='store_true',help='Um ciclo público, preservando carteira e cancelando pendências ao sair')
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',args.session) or not 1<=args.hours<=24 or not 5<=args.poll_seconds<=60:parser.error('Sessão/horas/intervalo inválidos.')
    session=None
    try:
        cfg=load_settings()
        if cfg.mode!='paper':raise ConfigError('Esta orquestração exige TRADING_MODE=paper.')
        if args.order_budget is not None:cfg=replace(cfg,max_order_notional=args.order_budget)
        root=ROOT/'reports/local/spot-runs'/args.session
        with single_runner(root/'runner.lock'):
            session=PaperSession(root,cfg,PublicBinance(),hours=args.hours)
            print('Simulação separada de 20 USDT; nenhuma ordem real. Não feche o processo para manter a proteção sintética.',flush=True)
            failures=0
            try:
                while True:
                    try:
                        result=session.cycle();failures=0
                        if result['phase']=='STOPPED':break
                        if args.once:session.stop('ONE_CYCLE');break
                    except TransientDataError:
                        failures+=1;session.report('ERROR','PUBLIC_CONNECTION')
                        if failures>=5:raise DataError('Coleta indisponível após cinco ciclos; sessão encerrada.')
                    time.sleep(args.poll_seconds)
            except KeyboardInterrupt:session.stop('INTERRUPTED')
            except Exception:
                session.stop('FAILURE');raise
    except (DataError,StrategyError,RiskError,ExecutionError,ConfigError,OSError,ValueError):
        raise SystemExit('Sessão recusada/encerrada. Confira integridade, filtros, conexão, STOP e relatórios locais; saldo preservado.') from None


if __name__=='__main__':main()
