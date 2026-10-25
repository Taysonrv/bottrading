"""Bounded read-only V3 telemetry; never falls back to offline replay."""
import heapq
import json
from pathlib import Path
import time


def read(path):
    try:
        if path.stat().st_size>2000000:return {}
        value=json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):return {}


def load(root, now_ms=None):
    root=Path(root);now=int(time.time()*1000) if now_ms is None else now_ms
    report=read(root/'reports/local/v3-status/latest.json')
    age=now-report['updated_ms'] if type(report.get('updated_ms')) is int else None
    forward=report.get('source')=='PUBLIC_REST_FORWARD'
    fresh=forward and age is not None and 0<=age<=90000 and report.get('healthy') is True
    folder=root/'reports/local/shadow-log';paths=[]
    if folder.is_dir():paths=heapq.nlargest(50,folder.glob('*.json'),key=lambda p:p.name)
    shadows=[v for p in paths if (v:=read(p))]
    failures={}
    for r in shadows:
        reason=r.get('shadow_judgment',{}).get('reason','SHADOW_UNAVAILABLE')
        failures[reason]=failures.get(reason,0)+1
    assessed=[r for r in shadows if type(r.get('concordance')) is bool]
    return dict(available=bool(report),fresh=fresh,age_ms=age,forward_source=forward,
        feasibility=read(root/'reports/local/v3-feasibility/latest.json'),
        backtest=read(root/'reports/local/v3-backtest/latest.json'),
        single_exit=read(root/'reports/local/single-exit-research/latest.json'),
        report=report,shadow_recent=shadows,shadow_failed_reasons=failures,
        agreement_recent=sum(r['concordance'] for r in assessed)/len(assessed) if assessed else None,
        comparison_scope='Recent heuristic policy observations, not AI calibration or cumulative session accuracy.',
        execution_authorized=False,approved=False)
