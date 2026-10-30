"""Read-only projection of the shared wallet; never creates a database."""
from contextlib import closing
from decimal import Decimal as D, localcontext, DecimalException
import json
from pathlib import Path
import sqlite3
import time
from portfolio_backend import factory
from spot_engine.portfolio import Portfolio
from system_status import read


def load(root,now=None):
    try:broker=factory(root)
    except (OSError,ValueError):return dict(available=False,reason='INVALID_PORTFOLIO_PROFILE')
    now=time.time() if now is None else now
    if not broker.path.exists():return dict(available=False,reason='NOT_STARTED')
    try:
        with closing(sqlite3.connect(broker.path.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as db:
            row=db.execute('SELECT payload FROM ledger WHERE id=1').fetchone()
            if not row or len(row[0])>16000000:raise ValueError()
            s=json.loads(row[0])
            with localcontext() as context:
                context.prec=80
                broker._reconcile(s)
        report=read(broker.path.parent/'status.json')
        timestamp=report.get('updated_ms')
        fresh=type(timestamp) is int and 0<=now*1000-timestamp<60000 and report.get('phase')=='RUNNING'
        mark=report.get('equity')
        if mark is not None:
            try:
                checked=D(str(mark))
                if not checked.is_finite() or checked<0:mark=None
            except (DecimalException,ValueError):mark=None
        matches=all(report.get(k)==s[k] for k in ('cash','fees','realized','position','pending'))
        return dict(available=True,fresh=fresh and matches,mode='PAPER',real_orders=0,capital='20',
                    updated=timestamp/1000 if type(timestamp) is int else None,peak=s['peak'],
                    drawdown=str(max(D(0),1-D(str(mark))/D(s['peak']))) if matches and fresh and mark is not None else None,
                    phase=report.get('phase','NOT_STARTED'),reason=report.get('reason','NO_REPORT'),
                    cash=s['cash'],reserved=s['pending']['reserved'] if s['pending'] else '0',
                    equity=str(mark) if mark is not None and matches and fresh else None,
                    fees=s['fees'],realized=s['realized'],position=s['position'],pending=s['pending'],halt=s['halt'],
                    buy_fills=sum(f['side']=='BUY' for f in s['fills']),sell_fills=sum(f['side']=='SELL' for f in s['fills']),
                    orders=list(s['orders'].values())[-100:],fills=s['fills'][-100:])
    except (OSError,ValueError,KeyError,TypeError,IndexError,DecimalException,sqlite3.Error):
        return dict(available=False,reason='LEDGER_OR_IDENTITY_ERROR')
