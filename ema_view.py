"""Read-only, bounded projection of the EMA paper session for the dashboard."""
from contextlib import closing
from decimal import Decimal, InvalidOperation, localcontext
import json
import math
from pathlib import Path
import re
import sqlite3
import time


def numeric(value,nonnegative=False):
    if isinstance(value,bool):raise ValueError
    number=float(Decimal(str(value)))
    if not math.isfinite(number) or (nonnegative and number<0):raise ValueError
    return number


def timestamp(value):
    if type(value) is not int or value<0:raise ValueError
    return value/1000


def risk_status(folder):
    """Risk checkpoint has its own timestamp; don't imply wallet/DB atomicity."""
    path=folder/'reports/local/spot-risk/risk.sqlite'
    if not path.is_file():return {'available':False}
    try:
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as db:
            db.execute('PRAGMA query_only=ON')
            row=db.execute('SELECT substr(payload,1,65537) FROM checkpoint WHERE id=1').fetchone()
        if not row or len(row[0])>65536:raise ValueError
        state=json.loads(row[0]);updated=timestamp(state['last_ms'])
        if type(state['day']) is not int or state['day']!=state['last_ms']//86400000:raise ValueError
        if any(type(state[k]) is not bool for k in ('daily_halted','drawdown_halted','stop_active')):raise ValueError
        peak=numeric(state['peak'],True);base=numeric(state['day_equity'],True);equity=numeric(state['equity'],True)
        if min(peak,base)<=0 or peak<max(base,equity):raise ValueError
        return dict(available=True,updated=updated,drawdown=max(0,1-equity/peak),daily_loss=max(0,1-equity/base),
                    daily_halted=state['daily_halted'],drawdown_halted=state['drawdown_halted'],stop_active=state['stop_active'])
    except (OSError,ValueError,KeyError,TypeError,sqlite3.Error,InvalidOperation,OverflowError):return {'available':False}


def load(root,now=None):
    root=Path(root);folder=root/'reports/local/spot-runs/ema20'
    path=folder/'status.json';dbpath=folder/'reports/local/spot-execution/paper.sqlite'
    if not path.exists():return {'available':False,'status':'missing'}
    try:
        if path.stat().st_size>65536:raise ValueError
        s=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(s,dict) or s.get('mode')!='PAPER' or s.get('real_orders')!=0 or s.get('approved') is not False:raise ValueError
        if s.get('phase') not in ('RUNNING','ERROR','STOPPED'):raise ValueError
        if not re.fullmatch(r'[A-Z0-9]{2,15}/USDT',s['symbol']):raise ValueError
        report={'available':True,'status':'ok','phase':s['phase'],'symbol':s['symbol'],
                'updated':timestamp(s['updated_ms']),'end':timestamp(s['end_ms']),
                'last_signal':str(s.get('last_signal',''))[:80],
                'reason':str(s.get('reason',''))[:80],
                'capital':numeric(s['capital'],True),'order_budget':numeric(s['max_order_budget'],True),
                'equity':numeric(s['equity'],True) if s['equity'] is not None else None,
                'pnl':numeric(s['pnl']) if s['pnl'] is not None else None,
                'price_received':timestamp(s['price_received_ms']) if s.get('price_received_ms') is not None else None,
                'cash':numeric(s['cash'],True),'reserved':numeric(s['reserved'],True),'units':numeric(s['units'],True),
                'realized':numeric(s['realized']),'fees':numeric(s['fees'],True)}
        if not dbpath.is_file():raise ValueError
        with closing(sqlite3.connect(dbpath.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as db:
            db.execute('PRAGMA query_only=ON')
            row=db.execute('SELECT substr(payload,1,8388609) FROM ledger WHERE id=1').fetchone()
            if not row or len(row[0])>8388608:raise ValueError
            ledger=json.loads(row[0])
        if not isinstance(ledger,dict) or not isinstance(ledger.get('orders'),dict) or not isinstance(ledger.get('fills'),list):raise ValueError
        with localcontext() as context:
            context.prec=80
            cash=Decimal(str(s['capital']));units=cost=fees=realized=Decimal(0)
            for f in ledger['fills']:
                q=Decimal(f['quantity']);price=Decimal(f['price']);fee=Decimal(f['fee'])
                if not all(v.is_finite() for v in (q,price,fee)) or min(q,price)<=0 or fee<0:raise ValueError
                fees+=fee
                if f['side']=='BUY':cash-=q*price+fee;units+=q;cost+=q*price+fee
                elif f['side']=='SELL' and q<=units:
                    removed=cost if q==units else cost*q/units
                    cash+=q*price-fee;realized+=q*price-fee-removed;units-=q;cost-=removed
                else:raise ValueError
            if any(Decimal(ledger[k])!=v for k,v in dict(cash=cash,units=units,cost=cost,realized=realized,fees=fees).items()):raise ValueError
        report['in_transition']=any(numeric(ledger[k])!=report[k] for k in ('cash','reserved','units','realized','fees'))
        if report['in_transition']:report['equity']=report['pnl']=None
        for k in ('cash','reserved','units','fees'):report[k]=numeric(ledger[k],True)
        report['realized']=numeric(ledger['realized']);report['cost']=numeric(ledger['cost'],True)
        if report['reserved']>report['cash']:raise ValueError
        report['protection']=None
        if ledger['protection'] is not None:
            report['protection']={k:numeric(ledger['protection'][k],True) for k in ('stop','take')}
            if not 0<report['protection']['stop']<report['protection']['take']:raise ValueError
        report['orders']=[]
        for key,o in list(ledger['orders'].items())[-100:]:
            if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',key):raise ValueError
            if o['side'] not in ('BUY','SELL') or o['status'] not in ('NEW','PARTIAL','FILLED','CANCELED','REJECTED'):raise ValueError
            report['orders'].append(dict(id=key,side=o['side'],status=o['status'],time=timestamp(o['created_ms']),
                quantity=numeric(o['quantity'],True),filled=numeric(o['filled'],True),price=numeric(o['limit'],True),reason=str(o['reason'])[:80]))
        report['fills']=[]
        for f in ledger['fills'][-100:]:
            if f['side'] not in ('BUY','SELL'):raise ValueError
            report['fills'].append(dict(time=timestamp(f['time_ms']),side=f['side'],quantity=numeric(f['quantity'],True),price=numeric(f['price'],True),fee=numeric(f['fee'],True)))
        report['buy_fills']=sum(f['side']=='BUY' for f in ledger['fills'])
        report['sell_fills']=sum(f['side']=='SELL' for f in ledger['fills'])
        age=(time.time() if now is None else now)-report['updated']
        report['age_seconds']=age if age>=0 else None
        report['fresh']=s['phase']=='RUNNING' and 0<=age<60
        report['risk']=risk_status(folder)
        report['active_order_id']=ledger.get('active')
        if report['active_order_id'] is not None and report['active_order_id'] not in ledger['orders']:raise ValueError
        report['stop']=(root/'STOP').exists() or (folder/'STOP').exists()
        return report
    except (OSError,ValueError,KeyError,TypeError,sqlite3.Error,InvalidOperation,OverflowError):
        return {'available':False,'status':'invalid'}
