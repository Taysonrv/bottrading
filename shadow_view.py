"""Expose only the reviewed offline-demo summary, never journal rows or secrets."""
import json
import math
from pathlib import Path


def load(root):
    path=Path(root)/'reports/local/ai-shadow-offline/demo-report.json'
    try:
        saved_at=path.stat().st_mtime
        report=json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:return {'status':'missing'}
    except (OSError,ValueError):return {'status':'invalid'}
    if not isinstance(report,dict):return {'status':'invalid'}
    if report.get('mode')!='OFFLINE_FIXTURE' or not all(report.get(k) is True for k in ('synthetic_prices','synthetic_account','synthetic_response')):
        return {'status':'invalid'}
    if report.get('provider_enabled') is not False or report.get('trading_enabled') is not False or any(type(report.get(k)) is not int or report[k]!=0 for k in ('orders','requests_paid')):
        return {'status':'invalid'}
    state=report.get('state',{});decision=report.get('decision',{});review=report.get('review',{})
    if not all(isinstance(v,dict) for v in (state,decision,review)):return {'status':'invalid'}
    if decision.get('action') not in ('HOLD','REVIEW_REQUIRED','SHADOW_CANDIDATE') or decision.get('trading_enabled') is not False:
        return {'status':'invalid'}
    def number(value):
        return value if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) else None
    return dict(status='available',saved_at=saved_at,mode='OFFLINE_FIXTURE',orders=0,requests_paid=0,
                action=decision['action'],symbol=state.get('symbol') if state.get('symbol') in ('BTCUSDT','ETHUSDT') else None,
                features={k:number(state.get(k)) for k in ('mid','spread','imbalance_l1','volatility','drawdown','daily_loss','cutoff')},
                token_count_verified=state.get('token_count_verified') is True,
                verdict='INCONCLUSIVO',mature_labels=number(review.get('mature_labels')),
                trading_enabled=False,provider_enabled=False)
