"""Heuristic policy observation, NOT AI inference or calibrated probabilities.

Missing account/risk/flow data blocks the shadow policy. Never updates the
original AI risk journal and never turns shadow agreement into permission.
"""
import json
from pathlib import Path
import time
import uuid
from ai_shadow.policy import judge


def build_shadow_input(v3_signal, market_state, portfolio_state=None):
    s=v3_signal.report() if hasattr(v3_signal,'report') else v3_signal
    score=s['score']
    if type(score) is not int or not 0<=score<=100:raise ValueError('INVALID_SCORE')
    proxy=score/100
    # Satisfies the existing contract's confidence transformation algebraically.
    # These values are explicitly uncalibrated heuristic placeholders.
    selected=(1+2*proxy)/3
    probabilities=dict(long=selected,short=(1-selected)/2,neutral=(1-selected)/2)
    raw=dict(regime={'TREND':'trending','BREAKOUT':'trending','RANGE':'mean_reverting',
        'CRISIS':'crisis'}.get(s['regime'],'high_vol'),direction='long',
        probabilities=probabilities,confidence=proxy,toxic_flow=True,
        setup_quality=min(3,score//25),risk_state='reduce',model='HEURISTIC_NOT_AI',schema='v3-proxy-1')
    return dict(raw=raw,risk=dict(eligible=False,reason='UNVERIFIED_ACCOUNT_AND_FLOW'),
        calibration='NOT_CALIBRATED',execution_authorized=False)


def shadow_observe(v3_signal, market_state, portfolio_state=None, *, log_dir=None):
    try:
        inputs=build_shadow_input(v3_signal,market_state,portfolio_state)
        result=judge(inputs['raw'],inputs['risk'])
        result.update(trading_enabled=False,kelly_enabled=False,execution_authorized=False)
        s=v3_signal.report() if hasattr(v3_signal,'report') else v3_signal
        row=dict(timestamp_ms=int(time.time()*1000),v3_signal=s,
            shadow_input=inputs,shadow_judgment=result,
            concordance=result['action']=='SHADOW_CANDIDATE',
            comparison_scope='HEURISTIC_POLICY_ONLY_NOT_PREDICTIVE_AGREEMENT',execution_authorized=False)
        if log_dir is not None:
            folder=Path(log_dir);folder.mkdir(parents=True,exist_ok=True)
            with (folder/(str(row['timestamp_ms'])+'-'+uuid.uuid4().hex+'.json')).open('x',encoding='utf-8') as out:
                json.dump(row,out,allow_nan=False)
        return row
    except Exception:
        # Safe structured error, no provider text, secrets or trading fallback.
        return dict(status='SHADOW_UNAVAILABLE',execution_authorized=False,
                    trading_enabled=False,kelly_enabled=False,concordance=None)
