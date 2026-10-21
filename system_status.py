"""One read-only view of operational scope; saved RUNNING is not liveness."""
import json
import math
from pathlib import Path
import time


def read(path):
    try:
        if path.stat().st_size>1_000_000:return {}
        result=json.loads(path.read_text(encoding='utf-8'))
        return result if isinstance(result,dict) else {}
    except (OSError,ValueError):return {}


def build(root,now=None):
    root=Path(root);now=time.time() if now is None else now
    ema=read(root/'reports/local/spot-runs/ema20/status.json')
    market=read(root/'reports/local/multipair.json')
    supervisor=read(root/'reports/local/system-run.json')
    def age(value):
        if type(value) not in (int,float) or not math.isfinite(value) or value<0:return None
        delta=now-value/1000
        return delta if delta>=0 else None
    pairs=market.get('pairs')
    valid_pairs=isinstance(pairs,list) and len(pairs)==6 and all(isinstance(p,dict) and p.get('status')=='OK' for p in pairs)
    ea=age(ema.get('updated_ms'));ma=age(market.get('updated_ms'));sa=age(supervisor.get('updated_ms'))
    return dict(mode='PAPER',real_orders_enabled=False,multipair_execution_enabled=False,
                controller=dict(phase=supervisor.get('phase','NOT_STARTED'),fresh=sa is not None and sa<30 and supervisor.get('phase')=='RUNNING',age_seconds=sa),
                execution=dict(symbol='BTC/USDT',timeframe='1h',fresh=ea is not None and ea<60 and ema.get('phase')=='RUNNING',age_seconds=ea,
                               phase=ema.get('phase','NOT_STARTED'),reason=ema.get('reason'),end_ms=ema.get('end_ms')),
                market=dict(symbols=['BTC/USDT','ETH/USDT','SOL/USDT','BNB/USDT','XRP/USDT','DOGE/USDT'],timeframe=market.get('timeframe','15m'),
                            fresh=ma is not None and ma<180 and valid_pairs,age_seconds=ma),
                research=dict(role='OFFLINE_ONLY',execution_authorized=False),
                kronos=dict(role='OBSERVATION_ONLY',execution_authorized=False),
                note='Controller health and persisted wallet state are distinct. Multi-pair shared-wallet execution is not implemented.')
