"""Read the full reconciled paper ledger, never initialize or reset it."""
from decimal import Decimal as D
import time
from spot_engine.risk import decimal_policy
from portfolio_alerts import ledger
from system_status import read


@decimal_policy
def load(root,book,now_ms):
    s=ledger(root);now_ms=int(time.time()*1000)
    if type(s.get('last_ms')) is not int or s['last_ms']>now_ms:raise ValueError('FUTURE_LEDGER_TIMESTAMP')
    pos=s['position'];cash=D(s['cash'])
    marked=D(0)
    if pos:
        if pos['symbol']!=book['symbol']:raise ValueError('INVENTORY_MARK_UNAVAILABLE')
        marked=D(pos['quantity'])*D(str(book['bid']))*D('.999')*D('.999')
    equity=cash+marked
    if equity<=0:raise ValueError('NONPOSITIVE_EQUITY')
    if D(s['peak'])<=0 or D(s['day_equity'])<=0:raise ValueError('INVALID_RISK_CHECKPOINT')
    peak=max(D(s['peak']),equity)
    dd=max(D(0),1-equity/peak)
    daily=max(D(0),1-equity/D(s['day_equity'])) if s['day']==now_ms//86400000 else None
    report=read(root/'reports/local/portfolio/status.json')
    plan=read(root/'reports/local/portfolio/plan.json')
    stamp=report.get('updated_ms')
    active=(report.get('phase')=='RUNNING' and type(stamp) is int and 0<=now_ms-stamp<60000
        and type(plan.get('end_ms')) is int and now_ms<plan['end_ms'] and not s['halt'])
    return dict(equity=str(equity),cash=str(cash),inventory_fraction=float(marked/equity),
        drawdown=float(dd),daily_loss=float(daily) if daily is not None else None,
        session_active=active,positions=int(bool(pos)),pending=int(bool(s['pending'])),
        ledger_halt=s['halt'],phase=report.get('phase','UNKNOWN'),source='RECONCILED_PAPER_LEDGER',
        account_received_ms=now_ms,ledger_ms=s['last_ms'])
