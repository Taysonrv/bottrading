"""Read-only control-plane projection, separate from trading PnL and fixtures."""
import json
from pathlib import Path
import time


def read(path):
    try:
        if path.stat().st_size>2000000:return {}
        d=json.loads(path.read_text(encoding='utf-8'))
        return d if isinstance(d,dict) else {}
    except (OSError,ValueError):return {}


def load(root,now_ms=None):
    folder=Path(root)/'reports/local/quant-control'
    r=read(folder/'latest.json');review=read(folder/'review-latest.json')
    now=int(time.time()*1000) if now_ms is None else now_ms
    t=r.get('updated_ms');age=now-t if type(t) is int else None
    fresh=age is not None and 0<=age<90000 and r.get('healthy') is True
    return dict(available=bool(r),fresh=fresh,age_ms=age,report=r,review=review,
        execution_authorized=False,provider_enabled=False)
