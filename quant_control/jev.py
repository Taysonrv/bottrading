"""Documented Jev request and response adapter. Intentionally no HTTP transport.

Source: https://docs.typesafe.ai/introduction/quickstart and /confidence.
No API key, calls, paid inference or fabricated response in the live service.
"""
from .contracts import validate


def request(snapshot):
    payload=dict(model='jev-latest',state=snapshot['encoded'],questions={
        'regime':dict(type='choice',instructions='Classify only the observed market state; uncertainty favors crisis/high_vol.',
            criteria=dict(trending='Directional trend supported by state.',mean_reverting='Range with reversion evidence.',
                          high_vol='Volatile or insufficient context.',crisis='Disorderly conditions.')),
        'direction':dict(type='choice',instructions='Judge next-hour direction after round-trip costs. Not an order or guarantee.',
            criteria=dict(long='Positive long net return.',short='Negative directional move; Spot short forbidden.',neutral='No supported net edge.')),
        # Choice produces a discrete level. Jev Score can return fractional
        # values, so do not silently truncate it into this integer contract.
        'setup_quality':dict(type='choice',instructions='Choose exactly one setup quality level.',
            criteria={'0':'No evidence','1':'Weak','2':'Supported candidate','3':'Strong supported candidate'}),
        'toxic_flow':dict(type='choice',instructions='Is flow toxic or unverifiable? L1 alone does not establish flow safety.',
            criteria={'true':'Toxic or unverified flow','false':'Observed flow evidence supports safety'}),
        'risk_state':dict(type='choice',instructions='Classify supplied deterministic risk readings; missing values require reduce.',
            criteria=dict(safe='Verified within limits.',near_limit='Approaching limits.',reduce='Limit hit or missing readings.'))})
    legend=('State v1: s=0 BTC,1 ETH,2 SOL,3 BNB; t=cutoff and b=closed bar end in UTC ms; '
            'mid=USDT price; spr=spread fraction; imb=L1 imbalance; rv=15m log-return std60; '
            'r1/r4/r60=returns over1/4/60 closed15m bars; atr=Wilder14 fraction; '
            'inv=inventory fraction,dd=drawdown,dl=daily loss; null=unknown. '
            'L1 does not verify flow. No fundamentals are supplied. ')
    for q in payload['questions'].values():q['instructions']=legend+q['instructions']
    return payload


def parse(response,schema='quant-schema-1'):
    answers=response['answers']
    if set(answers)!=set(('regime','direction','setup_quality','toxic_flow','risk_state')):
        raise ValueError('JEV_ANSWER_KEYS')
    for name,keys in [('regime',{'trending','mean_reverting','high_vol','crisis'}),
        ('direction',{'long','short','neutral'}),('setup_quality',{'0','1','2','3'}),
        ('toxic_flow',{'true','false'}),('risk_state',{'safe','near_limit','reduce'})]:
        a=answers[name]
        if a.get('type')!='choice' or a.get('choice') not in keys:raise ValueError('JEV_CHOICE_TYPE')
        from .state import numeric
        import math
        ps=a.get('probabilities',{})
        if set(ps)!=keys:raise ValueError('JEV_PROBABILITY_KEYS')
        for p in ps.values():numeric(p,0,1)
        if not math.isclose(sum(ps.values()),1,abs_tol=1e-8) or ps[a['choice']]!=max(ps.values()):raise ValueError('JEV_DISTRIBUTION')
        expected=(max(ps.values())-1/len(keys))/(1-1/len(keys))
        if not math.isclose(numeric(a.get('confidence'),0,1),expected,abs_tol=1e-8):raise ValueError('JEV_CONFIDENCE')
    d=answers['direction']
    return validate(dict(regime=answers['regime']['choice'],direction=d['choice'],
        probabilities=d['probabilities'],confidence=d['confidence'],
        toxic_flow=answers['toxic_flow']['choice']=='true',
        setup_quality=int(answers['setup_quality']['choice']),risk_state=answers['risk_state']['choice'],
        model=response['model'],schema=schema))


class DisabledProvider:
    name='NOT_CONFIGURED'
    def evaluate(self,snapshot):
        return dict(status='PROVIDER_NOT_CONFIGURED',decision=None,provider_enabled=False,
                    requests_paid=0,latency_ms=None,execution_authorized=False)
