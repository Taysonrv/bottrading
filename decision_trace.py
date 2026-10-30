"""Immutable whitelisted decision evidence, separate from money and credentials."""
import hashlib
import json
import os
from pathlib import Path

SIGNAL_FIELDS=('symbol','status','action','reason','candle_close_ms','close','ema_fast','ema_slow','ema_trend','atr_fraction')
QUOTE_FIELDS=('bid','ask','received_ms','min_notional','qty_step','price_tick','cash_before','halt_before','candidate')


def path_for(root,identity,phase,key):
    token=hashlib.sha256(json.dumps([identity,phase,key],separators=(',',':')).encode()).hexdigest()
    return Path(root)/'reports/local/decision-trace'/(token+'.json')


def record(root,identity,phase,key,now_ms,row,*,quote=None,outcome=None):
    if phase not in ('SIGNAL','ENTRY_INTENT','RESERVATION'):raise ValueError('TRACE_PHASE')
    if type(now_ms) is not int or now_ms<0:raise ValueError('TRACE_CLOCK')
    close=row.get('candle_close_ms')
    if type(close) is not int or not 0<=close<=now_ms:raise ValueError('TRACE_FUTURE_SIGNAL')
    signal={k:row.get(k) for k in SIGNAL_FIELDS}
    value=dict(version=1,identity=identity,phase=phase,key=key,recorded_ms=now_ms,signal=signal,
        quote={k:quote.get(k) for k in QUOTE_FIELDS} if quote else None,outcome={k:outcome.get(k) for k in ('id','symbol','status','reason','quantity','limit','stop','take','reserved')} if outcome else None,
        execution_real=False)
    # Validate before opening a file: NaN, infinity or unsupported values leave no artifact.
    encoded=json.dumps(value,allow_nan=False,ensure_ascii=True,separators=(',',':'))
    if len(encoded.encode())>20000:raise ValueError('TRACE_SIZE_LIMIT')
    path=path_for(root,identity,phase,key);path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open('x',encoding='utf-8') as out:
            out.write(encoded);out.flush();os.fsync(out.fileno())
    except FileExistsError:
        old=lookup(root,identity,phase,key)
        if not old:raise ValueError('TRACE_EXISTING_RECORD_INVALID')
        if any(old.get(k)!=value[k] for k in ('signal','quote','outcome')):raise ValueError('TRACE_EVIDENCE_CONFLICT')
        return old
    return value


def lookup(root,identity,phase,key):
    path=path_for(root,identity,phase,key)
    try:
        if path.stat().st_size>20000:return None
        value=json.loads(path.read_text(encoding='utf-8'))
        return value if (value.get('identity'),value.get('phase'),value.get('key'))==(identity,phase,key) else None
    except (OSError,ValueError,AttributeError):return None
