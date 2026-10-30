"""Authenticated dashboard exports from the complete read-only reconciled ledger."""
import csv
from decimal import Decimal as D,InvalidOperation
import io
from portfolio_alerts import ledger
from spot_engine.risk import decimal_policy


def safe_cell(value):
    text=str(value if value is not None else '')
    stripped=text.lstrip()
    if stripped.startswith(('=','+','-','@')):
        try:numeric=D(stripped).is_finite()
        except InvalidOperation:numeric=False
        if not numeric:text="'"+text
    return text


@decimal_policy
def export(root,kind):
    if kind not in ('fills','cycles'):raise ValueError('EXPORT_KIND')
    state=ledger(root);rows=[]
    if kind=='fills':
        columns=('time_ms','symbol','side','order','quantity','price','fee','reason')
        rows=state['fills']
    else:
        columns=('symbol','entry_ms','exit_ms','quantity','entry','exit','fees','net_pnl','reason')
        position=None
        for f in state['fills']:
            if f['side']=='BUY':position=f
            elif position:
                cost=D(position['quantity'])*D(position['price'])+D(position['fee'])
                net=D(f['quantity'])*D(f['price'])-D(f['fee'])-cost
                rows.append(dict(symbol=f['symbol'],entry_ms=position['time_ms'],exit_ms=f['time_ms'],
                    quantity=f['quantity'],entry=position['price'],exit=f['price'],fees=str(D(position['fee'])+D(f['fee'])),
                    net_pnl=str(net),reason=f.get('reason')))
                position=None
        if sum((D(r['net_pnl']) for r in rows),D(0))!=D(state['realized']):raise ValueError('EXPORT_CASHFLOW')
    text=io.StringIO(newline='');writer=csv.writer(text,lineterminator='\r\n');writer.writerow(columns)
    for r in rows:writer.writerow([safe_cell(r.get(k)) for k in columns])
    return ('\ufeff'+text.getvalue()).encode('utf-8')
