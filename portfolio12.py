"""Single-cash, one-position PAPER ledger. No exchange client or credentials.

Entries reserve cash atomically; fills require a later supplied quote. Full fills
only: insufficient displayed liquidity produces no fill, not a fictional partial.
This module is deliberately independent of the active EMA wallet identity.
"""
from contextlib import contextmanager, closing
from dataclasses import asdict
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import sqlite3
from spot_engine.execution import floor, ceil, digest
from spot_engine.risk import Rules, amount, decimal_policy
from spot_engine.selection import preview

SYMBOLS=('BTC/USDT','ETH/USDT','SOL/USDT','BNB/USDT','XRP/USDT','DOGE/USDT','ADA/USDT','LINK/USDT','AVAX/USDT','LTC/USDT','DOT/USDT','NEAR/USDT')
FEE=D('.001'); SLIP=D('.001'); CAPITAL=D('20'); BUDGET=D('6')


class PortfolioError(ValueError): pass


class Portfolio:
    def __init__(self, root):
        self.root=Path(root)
        self.path=self.root/'reports/local/portfolio/paper.sqlite'
        self.identity=digest({name:hashlib.sha256((Path(__file__).parent/name).read_text(encoding='utf-8-sig').encode('utf-8')).hexdigest()
                              for name in ('portfolio12.py','portfolio12_run.py','spot_engine/selection.py','spot_engine/strategy.py','spot_engine/config.py','spot_engine/scanner.py','spot_engine/risk.py','spot_engine/execution.py','spot_engine/main.py','spot_engine/data.py')})

    def stopped(self):
        return (self.root/'STOP').exists() or (self.path.parent/'STOP').exists()

    def initialize(self, now_ms):
        self._time(now_ms)
        if self.stopped():raise PortfolioError('STOP')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        # Exclusive creation avoids two processes issuing the initial capital.
        with self.path.open('xb'): pass
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('CREATE TABLE ledger (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')
            s=dict(identity=self.identity,cash='20',cost='0',realized='0',fees='0',
                   position=None,pending=None,orders={},fills=[],events={},quotes={},
                   peak='20',day=now_ms//86400000,day_equity='20',halt=None,last_ms=now_ms)
            db.execute('INSERT INTO ledger VALUES(1,?)',(json.dumps(s),));db.commit()

    @staticmethod
    def _time(value):
        if type(value) is not int or value<0:raise PortfolioError('INVALID_TIME')

    @contextmanager
    def _transaction(self):
        if not self.path.is_file():raise PortfolioError('NOT_INITIALIZED')
        with closing(sqlite3.connect(self.path.resolve().as_uri()+'?mode=rw',uri=True,timeout=5)) as db:
            db.execute('PRAGMA synchronous=FULL');db.execute('BEGIN IMMEDIATE')
            try:
                s=json.loads(db.execute('SELECT payload FROM ledger WHERE id=1').fetchone()[0])
                self._reconcile(s)
                yield s
                self._reconcile(s)
                if len(s['events'])>100000:raise PortfolioError('HISTORY_LIMIT')
                db.execute('UPDATE ledger SET payload=? WHERE id=1',(json.dumps(s),));db.commit()
            except Exception:db.rollback();raise

    def _reconcile(self,s):
        if s['identity']!=self.identity:raise PortfolioError('IDENTITY_CHANGED')
        cash=CAPITAL;cost=fees=realized=units=D(0);symbol=None
        for f in s['fills']:
            q=D(f['quantity']);p=D(f['price']);fee=D(f['fee'])
            amount(q,positive=True);amount(p,positive=True);amount(fee)
            if f['symbol'] not in SYMBOLS or fee!=q*p*FEE:raise PortfolioError('INVALID_FILL')
            fees+=fee
            if f['side']=='BUY' and not units:
                symbol=f['symbol'];units=q;cost=q*p+fee;cash-=cost
            elif f['side']=='SELL' and q==units and symbol==f['symbol']:
                cash+=q*p-fee;realized+=q*p-fee-cost;units=cost=D(0);symbol=None
            else:raise PortfolioError('INVENTORY_MISMATCH')
        if any(D(s[k])!=v for k,v in dict(cash=cash,cost=cost,fees=fees,realized=realized).items()) or cash<0:
            raise PortfolioError('LEDGER_MISMATCH')
        pos=s['position']
        if bool(pos)!=bool(units):raise PortfolioError('POSITION_MISMATCH')
        if pos and (pos['symbol']!=symbol or D(pos['quantity'])!=units or not 0<D(pos['stop'])<D(pos['take'])):
            raise PortfolioError('PROTECTION_MISMATCH')
        pending=s['pending']
        if pending and (pos or D(pending['reserved'])>cash or pending['symbol'] not in SYMBOLS):
            raise PortfolioError('RESERVATION_MISMATCH')
        if pending and D(pending['reserved'])!=D(pending['quantity'])*D(pending['limit'])*(1+FEE):
            raise PortfolioError('RESERVATION_MISMATCH')

    def _clock(self,s,now):
        self._time(now)
        if now<s['last_ms']:raise PortfolioError('CLOCK_REVERSED')
        s['last_ms']=now

    def _market(self,rules,bid,ask,quote_ms,now):
        self._time(quote_ms);self._time(now)
        amount(bid,positive=True);amount(ask,positive=True)
        if not isinstance(rules,Rules) or rules.symbol not in SYMBOLS:raise PortfolioError('INVALID_RULES')
        if bid>ask or not 0<=now-quote_ms<=5000 or not 0<=now-rules.observed_ms<=3600000:
            raise PortfolioError('STALE_MARKET')

    def _risk(self,s,equity,now):
        peak=max(D(s['peak']),equity);s['peak']=str(peak)
        day=now//86400000
        if s['day']!=day:s['day']=day;s['day_equity']=str(equity)
        if equity<=peak*D('.90'):s['halt']='DRAWDOWN'
        elif equity<=D(s['day_equity'])*D('.97'):s['halt']=s['halt'] or 'DAILY_LOSS'
        # Halts are latched across recovery and UTC days; no automatic reset.
        if self.stopped():s['halt']=s['halt'] or 'STOP'

    @decimal_policy
    def reserve(self,client_id,row,rules,bid,ask,quote_ms,now_ms):
        if not isinstance(client_id,str) or not client_id or len(client_id)>100:raise PortfolioError('INVALID_ID')
        self._market(rules,bid,ask,quote_ms,now_ms)
        request=digest([row,asdict(rules),bid,ask,quote_ms])
        with self._transaction() as s:
            old=s['orders'].get(client_id)
            if old:
                if old['request']!=request:raise PortfolioError('ID_CONFLICT')
                return dict(old)
            self._clock(s,now_ms)
            if s['position'] or s['pending']:raise PortfolioError('POSITION_OR_ORDER_EXISTS')
            self._risk(s,D(s['cash']),now_ms)
            plan=preview(row,rules,bid,ask,now_ms=now_ms,quote_ms=quote_ms,cash=D(s['cash']),budget=BUDGET,stopped=bool(s['halt']))
            result=dict(request=request,symbol=rules.symbol,side='BUY',status='REJECTED',reason=plan['reason'])
            if plan['eligible']:
                entry=ceil(ask*(1+SLIP),rules.price_tick);q=D(plan['quantity'])
                stop=floor(entry*D('.98'),rules.price_tick)
                if stop<=0:raise PortfolioError('INVALID_STOP')
                if self.stopped():raise PortfolioError('STOP')
                result.update(status='NEW',reason='RESERVED',id=client_id,quantity=str(q),limit=str(entry),
                              stop=str(stop),take=str(ceil(entry*D('1.04'),rules.price_tick)),
                              reserved=str(q*entry*(1+FEE)),created_ms=now_ms,quote_ms=quote_ms)
                s['pending']=dict(result)
            s['orders'][client_id]=result
            return dict(result)

    def _cancel(self,s,reason):
        if s['pending']:
            s['orders'][s['pending']['id']].update(status='CANCELED',reason=reason)
            s['pending']=None

    @decimal_policy
    def quote(self,event_id,rules,bid,ask,available_quantity,quote_ms,now_ms,exit_signal=False):
        self._market(rules,bid,ask,quote_ms,now_ms);amount(available_quantity)
        if type(exit_signal) is not bool or not isinstance(event_id,str) or not event_id or len(event_id)>100:raise PortfolioError('INVALID_EVENT')
        request=digest([asdict(rules),bid,ask,available_quantity,quote_ms,exit_signal])
        with self._transaction() as s:
            if event_id in s['events']:
                old=s['events'][event_id]
                if old['request']!=request:raise PortfolioError('EVENT_CONFLICT')
                return old['result']
            self._clock(s,now_ms)
            if quote_ms<=s['quotes'].get(rules.symbol,-1):raise PortfolioError('QUOTE_REPLAY')
            s['quotes'][rules.symbol]=quote_ms
            pos=s['position'];pending=s['pending'];result='NO_FILL'
            if pos and pos['symbol']!=rules.symbol:return 'OTHER_SYMBOL'
            liquidation=floor(bid*(1-SLIP),rules.price_tick)
            equity=D(s['cash'])+(D(pos['quantity'])*liquidation*(1-FEE) if pos else D(0))
            self._risk(s,equity,now_ms)
            if self.stopped():self._cancel(s,'STOP');result='STOP_EXPOSED' if pos else 'STOP'
            elif pending:
                if exit_signal or s['halt'] or now_ms-pending['created_ms']>=60000:self._cancel(s,'SIGNAL_EXIT' if exit_signal else s['halt'] or 'EXPIRED')
                elif pending['symbol']==rules.symbol:
                    price=ceil(ask*(1+SLIP),rules.price_tick);q=D(pending['quantity'])
                    if bid<=D(pending['stop']):self._cancel(s,'ENTRY_BELOW_STOP')
                    elif quote_ms>pending['quote_ms'] and quote_ms>=pending['created_ms']+500 and price<=D(pending['limit']) and available_quantity>=q:
                        if self._filters(rules,q,price):
                            if self.stopped():raise PortfolioError('STOP')
                            cost=q*price*(1+FEE);s['cash']=str(D(s['cash'])-cost);s['cost']=str(cost)
                            s['position']=dict(symbol=rules.symbol,quantity=str(q),stop=pending['stop'],take=pending['take'],opened_ms=quote_ms)
                            self._fill(s,event_id,pending['id'],'BUY',rules.symbol,q,price,now_ms)
                            s['orders'][pending['id']]['status']='FILLED';s['pending']=None;result='BUY_FILLED'
            elif pos and (pos.get('exit_request') or exit_signal or bid<=D(pos['stop']) or bid>=D(pos['take']) or s['halt']):
                if not pos.get('exit_request'):
                    reason='SIGNAL_EXIT' if exit_signal else 'STOP_LOSS' if bid<=D(pos['stop']) else 'TAKE_PROFIT' if bid>=D(pos['take']) else 'RISK_EXIT'
                    pos['exit_request']=dict(created_ms=quote_ms,reason=reason)
                q=D(pos['quantity'])
                # Synthetic exit gets a later tick, adverse bid slippage and no
                # guaranteed fill. No sale at the stop price across a gap.
                if quote_ms>=pos['exit_request']['created_ms']+500 and available_quantity>=q and self._filters(rules,q,liquidation):
                    if self.stopped():raise PortfolioError('STOP')
                    proceeds=q*liquidation*(1-FEE)
                    s['cash']=str(D(s['cash'])+proceeds);s['realized']=str(D(s['realized'])+proceeds-D(s['cost']))
                    s['cost']='0';s['position']=None
                    reason=pos['exit_request']['reason']
                    self._fill(s,event_id,event_id,'SELL',rules.symbol,q,liquidation,now_ms,reason);result='SELL_FILLED'
                else:result='EXIT_PENDING' if quote_ms<pos['exit_request']['created_ms']+500 else 'EXIT_FILTER_OR_LIQUIDITY'
            pos=s['position']
            equity=D(s['cash'])+(D(pos['quantity'])*liquidation*(1-FEE) if pos else D(0))
            self._risk(s,equity,now_ms)
            s['events'][event_id]=dict(request=request,result=result)
            return result

    @staticmethod
    def _filters(rules,q,price):
        return (rules.min_qty<=q<=rules.max_qty and q%rules.qty_step==0 and
                rules.min_price<=price<=rules.max_price and price%rules.price_tick==0 and
                rules.min_notional<=q*price<=rules.max_notional)

    @staticmethod
    def _fill(s,event,order,side,symbol,q,p,now,reason=None):
        fee=q*p*FEE;s['fees']=str(D(s['fees'])+fee)
        s['fills'].append(dict(event=event,order=order,side=side,symbol=symbol,quantity=str(q),price=str(p),fee=str(fee),time_ms=now,reason=reason))

    @decimal_policy
    def snapshot(self):
        with self._transaction() as s:return json.loads(json.dumps(s))

    @decimal_policy
    def cancel_pending(self,reason):
        with self._transaction() as s:self._cancel(s,reason)
