"""Causal net-outcome labels and multiclass Brier for supplied model records.

No caller may interpret this statistic as permission to trade or a Kelly input
without independent out-of-sample validation of the specified payoff target.
"""
import math
from .contracts import validate
from .state import numeric
from . import SYMBOLS


def mature(record,entry,exit,as_of_ms,fee=.001,slip=.001):
    d=validate(record['decision'])
    if record.get('symbol') not in SYMBOLS:raise ValueError('LABEL_SYMBOL')
    if record.get('source')!='REAL_PROVIDER_RESPONSE':return None
    predicted=record['predicted_ms']
    if type(predicted) is not int or type(as_of_ms) is not int or predicted>as_of_ms:raise ValueError('INVALID_LABEL_CLOCK')
    for q in (entry,exit):
        if q is None:return None
        for key in ('time_ms','received_ms'):
            if type(q.get(key)) is not int:return None
        if not q['time_ms']<=q['received_ms']<=as_of_ms or q['received_ms']-q['time_ms']>5000:return None
        for key in ('bid','ask'):numeric(q[key],1e-12)
        if q['bid']>q['ask']:raise ValueError('CROSSED_LABEL_QUOTE')
    if not predicted<entry['time_ms']<=predicted+5000:return None
    if not entry['time_ms']+3600000<=exit['time_ms']<=entry['time_ms']+3605000:return None
    numeric(fee,0,.01);numeric(slip,0,.01)
    long_return=exit['bid']*(1-fee)*(1-slip)/(entry['ask']*(1+fee)*(1+slip))-1
    short_return=entry['bid']*(1-fee)*(1-slip)/(exit['ask']*(1+fee)*(1+slip))-1
    outcome='long' if long_return>0 else 'short' if short_return>0 else 'neutral'
    return dict(symbol=record['symbol'],model=d['model'],schema=d['schema'],predicted_ms=predicted,label_ms=exit['received_ms'],
        label_spec=f'net-1h-fee{fee:.8g}-slip{slip:.8g}',
        outcome=outcome,probabilities=d['probabilities'],long_net_return=long_return,
        short_is_diagnostic_only=True,source='REAL_PROVIDER_RESPONSE',execution_authorized=False)


def report(rows,as_of_ms,model,schema):
    values=[];seen=set();label_spec=None
    for row in rows:
        if row.get('source')!='REAL_PROVIDER_RESPONSE' or row.get('model')!=model or row.get('schema')!=schema:
            raise ValueError('CALIBRATION_COHORT_MISMATCH')
        if not row['predicted_ms']<row['label_ms']<=as_of_ms:raise ValueError('IMMATURE_OR_FUTURE_LABEL')
        if row.get('symbol') not in SYMBOLS:raise ValueError('LABEL_SYMBOL')
        if not isinstance(row.get('label_spec'),str):raise ValueError('LABEL_SPEC')
        if label_spec is not None and label_spec!=row['label_spec']:raise ValueError('LABEL_COST_COHORT_MISMATCH')
        label_spec=row['label_spec']
        key=(row['symbol'],row['predicted_ms'])
        if key in seen:raise ValueError('DUPLICATE_LABEL')
        seen.add(key)
        ps=row['probabilities']
        if set(ps)!=set(('long','short','neutral')) or row['outcome'] not in ps:raise ValueError('LABEL_DOMAIN')
        for p in ps.values():numeric(p,0,1)
        if not math.isclose(sum(ps.values()),1,abs_tol=1e-8):raise ValueError('LABEL_PROBABILITY_SUM')
        values.append(math.fsum((p-float(k==row['outcome']))**2 for k,p in ps.items()))
    return dict(model=model,schema=schema,label_spec=label_spec,mature_labels=len(values),
        multiclass_brier=math.fsum(values)/len(values) if values else None,
        score_range=[0,2],status='MEASURED_NOT_APPROVED' if values else 'UNMEASURED',
        approved=False,kelly_enabled=False,execution_authorized=False,
        note='Overlapping horizons may be dependent. Brier alone is not trading edge or payoff validation.')


def quarter_kelly_research(p_win,average_win,average_loss):
    """Hypothetical only: probability must target the same net payoff distribution."""
    numeric(p_win,0,1);numeric(average_win,1e-12);numeric(average_loss,1e-12)
    ratio=average_win/average_loss
    fraction=max(0.,min(.25,.25*(p_win-(1-p_win)/ratio)))
    return dict(fraction=fraction,execution_authorized=False,kelly_enabled=False,
        note='Research arithmetic only; direction confidence is not a calibrated win probability.')
