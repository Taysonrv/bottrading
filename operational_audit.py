"""Read-only operational evidence. Stale heartbeats do not prove a failure cause."""
from decimal import Decimal as D
from pathlib import Path
import json
import sqlite3
import time
from portfolio_alerts import ledger
from spot_engine.risk import decimal_policy
from system_status import read


def recent_events(path):
    try:
        # Bound reads even if the journal has not yet rotated.
        with path.open('rb') as f:
            f.seek(0,2);size=f.tell();f.seek(max(0,size-64000));raw=f.read()
        lines=raw.splitlines()
        if size>64000:lines=lines[1:]
        rows=[]
        for line in lines:
            try:r=json.loads(line)
            except ValueError:continue
            if isinstance(r,dict):rows.append({k:r[k] for k in ('time_ms','kind','component','exit_code','reason','attempt') if k in r})
        return rows[-30:]
    except OSError:return []


@decimal_policy
def load(root,now_ms=None):
    root=Path(root);now=int(time.time()*1000) if now_ms is None else now_ms
    folder=root/'reports/local';control=read(folder/'system-run.json')
    status=read(folder/'portfolio/status.json');radar=read(folder/'portfolio/radar.json')
    def age(record):
        stamp=record.get('updated_ms')
        return (now-stamp)/1000 if type(stamp) is int and 0<=stamp<=now else None
    ca,ea,ra=age(control),age(status),age(radar)
    end=status.get('end_ms');expired=type(end) is int and end<=now
    stopped=(root/'STOP').exists() or (folder/'portfolio/STOP').exists()
    state='STOP' if stopped else 'ENDED' if expired else 'ENGINE_UNCONFIRMED' if ea is None or ea>=60 else 'ENGINE_STOPPED' if status.get('phase')!='RUNNING' else 'SUPERVISOR_UNCONFIRMED' if ca is None or ca>=30 else 'RECENT_REPORTS'
    events=recent_events(folder/'supervisor-events.jsonl')
    gaps=[r for r in events if r.get('kind')=='PREVIOUS_RUN_WITHOUT_SHUTDOWN_RECORD']
    result=dict(state=state,updated_ms=now,controller_age_seconds=ca,engine_age_seconds=ea,
        external_guard=read(folder/'external-guard.json'),
        radar_age_seconds=ra,execution_reason=status.get('reason'),deadline_ms=end,
        last_unexplained_gap=gaps[-1] if gaps else None,recent_events=events,
        recovery_attempts=control.get('recovery_attempts',{}),execution_authorized=False,
        ledger_available=False,trades=[],decisions=[],
        note='Freshness is based on saved reports, not an OS process probe. Missing shutdown evidence leaves cause unknown.')
    try:s=ledger(root)
    except (OSError,ValueError,KeyError,TypeError,ArithmeticError,sqlite3.Error):return result
    position=None;trades=[]
    for f in s['fills']:
        if f['side']=='BUY':position=f
        elif position:
            cost=D(position['quantity'])*D(position['price'])+D(position['fee'])
            net=D(f['quantity'])*D(f['price'])-D(f['fee'])-cost
            trades.append(dict(symbol=f['symbol'],entry_ms=position['time_ms'],exit_ms=f['time_ms'],
                entry=position['price'],exit=f['price'],quantity=f['quantity'],
                fees=str(D(position['fee'])+D(f['fee'])),net_pnl=str(net),reason=f.get('reason') or 'NOT_RECORDED',
                entry_indicators='NOT_RECORDED_AT_ORDER_TIME'))
            position=None
    evaluations=radar.get('selection',{}).get('previews',[])
    for row in radar.get('pairs',[]):
        if not isinstance(row,dict):continue
        preview=next((p for p in evaluations if p.get('symbol')==row.get('symbol')), {})
        # Explicit branches avoid treating a fresh radar as evidence that risk gates passed.
        if stopped:reason='STOP'
        elif expired:reason='SESSION_ENDED'
        elif s.get('halt'):reason=s['halt']
        elif ra is None or ra>=180:reason='STALE_RADAR'
        elif s['position'] or s['pending']:reason='POSITION_OR_ORDER_EXISTS'
        else:reason=preview.get('reason') or row.get('reason') or 'NOT_RECORDED'
        result['decisions'].append(dict(symbol=row.get('symbol'),action=row.get('action'),
            signal_reason=row.get('reason'),context_reason=reason,
            candle_close_ms=row.get('candle_close_ms'),status=row.get('status'),
            scope='CURRENT_RADAR_CONTEXT_NOT_HISTORICAL_ORDER_CAUSE'))
    result.update(ledger_available=True,total_closed_cycles=len(trades),trades=trades[-30:],
        total_fills=len(s['fills']),total_orders=len(s['orders']),cash=s['cash'],realized=s['realized'],fees=s['fees'])
    return result
