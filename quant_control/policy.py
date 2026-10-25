"""Hard gates compose in code. This control plane cannot authorize orders."""
from .contracts import validate


def assess(snapshot,raw,context):
    failed=[];passed=[];review=[]
    def gate(name,condition):
        (passed if condition else failed).append(name)
    gate('STOP_CLEAR',context.get('stopped') is False)
    gate('FRESH_STATE',context.get('fresh') is True)
    gate('MODEL_STATE_FRESH',context.get('decision_state_fresh') is True)
    state=snapshot.get('numeric',{})
    dd=state.get('dd');dl=state.get('dl')
    gate('DRAWDOWN_UNDER_10_PERCENT',type(dd) in (float,int) and 0<=dd<.10)
    gate('DAILY_LOSS_UNDER_3_PERCENT',type(dl) in (float,int) and 0<=dl<.03)
    gate('SESSION_ACTIVE',context.get('session_active') is True)
    gate('POSITION_LIMIT_CLEAR',type(context.get('positions')) is int and context['positions']==0
         and type(context.get('pending')) is int and context['pending']==0)
    inv=state.get('inv')
    gate('INVENTORY_UNDER_40_PERCENT',type(inv) in (float,int) and 0<=inv<=.40)
    gate('RISK_LEDGER_CLEAR',context.get('risk_ledger_clear') is True)
    gate('HISTORICAL_EDGE_VALIDATED',context.get('edge_validated') is True)
    gate('PROVIDER_CALIBRATED',context.get('calibration_verified') is True)
    gate('FLOW_VERIFIED',snapshot.get('flow_verified') is True)
    gate('TOKEN_BUDGET_VERIFIED',snapshot.get('token_count_verified') is True
         and type(snapshot.get('token_count')) is int and snapshot['token_count']<400)
    decision=None
    try:decision=validate(raw)
    except (ValueError,TypeError,KeyError):failed.append('VALID_TYPED_DECISION')
    if decision:
        passed.append('VALID_TYPED_DECISION')
        gate('LONG_SPOT_ONLY',decision['direction']=='long')
        gate('QUALITY_AT_LEAST_2',decision['setup_quality']>=2)
        gate('CONFIDENCE_ABOVE_080',decision['confidence']>.80)
        gate('RISK_SAFE',decision['risk_state']=='safe')
        gate('NONTOXIC_FLOW',decision['toxic_flow'] is False)
        gate('NONCRISIS_REGIME',decision['regime']!='crisis')
        if decision['confidence']<.60:review.append('LOW_CONFIDENCE')
        if decision['regime']=='crisis':review.append('CRISIS_REGIME')
    else:review.append('PROVIDER_OR_CONTRACT_UNAVAILABLE')
    return dict(action='REVIEW_REQUIRED' if review else 'HOLD' if failed else 'RESEARCH_CANDIDATE',
        gates_passed=passed,gates_failed=failed,review_reasons=review,
        setup_quality=decision['setup_quality'] if decision else None,
        confidence=decision['confidence'] if decision else None,
        kelly_enabled=False,kelly_fraction=None,execution_authorized=False,approved=False,
        note='Research decision only. Every broker order still needs its own deterministic risk check.')
