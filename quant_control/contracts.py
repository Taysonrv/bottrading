"""Strict decision contract; model outputs never contain sizes or order calls."""
import math
from .state import numeric

FIELDS={'regime','direction','probabilities','confidence','toxic_flow','setup_quality','risk_state','model','schema'}


def validate(raw):
    if not isinstance(raw,dict) or set(raw)!=FIELDS:raise ValueError('DECISION_FIELDS')
    if raw['regime'] not in ('trending','mean_reverting','high_vol','crisis'):raise ValueError('REGIME_ENUM')
    if raw['direction'] not in ('long','short','neutral'):raise ValueError('DIRECTION_ENUM')
    if raw['risk_state'] not in ('safe','near_limit','reduce'):raise ValueError('RISK_ENUM')
    if type(raw['toxic_flow']) is not bool:raise ValueError('FLOW_BOOL')
    if type(raw['setup_quality']) is not int or not 0<=raw['setup_quality']<=3:raise ValueError('QUALITY_0_TO_3')
    probabilities=raw['probabilities']
    if not isinstance(probabilities,dict) or set(probabilities)!=set(('long','short','neutral')):
        raise ValueError('PROBABILITY_FIELDS')
    for p in probabilities.values():numeric(p,0,1)
    if not math.isclose(math.fsum(probabilities.values()),1,abs_tol=1e-8):raise ValueError('PROBABILITY_SUM')
    selected=probabilities[raw['direction']]
    if selected!=max(probabilities.values()):raise ValueError('INCONSISTENT_DIRECTION')
    confidence=numeric(raw['confidence'],0,1)
    expected=(selected-1/3)/(1-1/3)
    if not math.isclose(confidence,expected,abs_tol=1e-8):raise ValueError('CHOICE_CONFIDENCE_INCONSISTENT')
    for k in ('model','schema'):
        if not isinstance(raw[k],str) or not 1<=len(raw[k])<=80:raise ValueError('MODEL_SCHEMA_VERSION')
    return {**raw,'probabilities':dict(probabilities)}
