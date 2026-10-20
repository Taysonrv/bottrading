from .contracts import decision


def judge(raw,risk,journal=None):
    result=dict(action='HOLD',reason='INVALID_DECISION',trading_enabled=False,kelly_enabled=False)
    try:d=decision(raw)
    except (ValueError,TypeError):return result
    if not isinstance(risk,dict) or risk.get('eligible') is not True:result['reason']=risk.get('reason','RISK_BLOCKED') if isinstance(risk,dict) else 'INVALID_RISK'
    elif d['regime']=='crisis' or d['confidence']<.60:
        result.update(action='REVIEW_REQUIRED',reason='MODEL_REVIEW')
        if journal is not None:journal.put('review_required',True)
    elif d['direction']!='long':result['reason']='NO_SPOT_LONG'
    elif d['setup_quality']<2 or d['confidence']<=.80 or d['risk_state']!='safe' or d['toxic_flow']:result['reason']='MODEL_GATE'
    else:result.update(action='SHADOW_CANDIDATE',reason='OFFLINE_ONLY')
    return result
