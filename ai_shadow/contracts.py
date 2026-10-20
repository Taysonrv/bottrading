import math


def numeric(value,minimum=None,maximum=None):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('Número finito obrigatório')
    if minimum is not None and value<minimum or maximum is not None and value>maximum:raise ValueError('Fora do domínio')
    return value


def fields(data,expected):
    if not isinstance(data,dict) or set(data)!=set(expected):raise ValueError('Campos inesperados ou ausentes')


def decision(data):
    fields(data,('regime','direction','probabilities','confidence','toxic_flow','setup_quality','risk_state','model','schema'))
    if data['regime'] not in ('trending','mean_reverting','high_vol','crisis'):raise ValueError('Regime inválido')
    if data['direction'] not in ('long','short','neutral'):raise ValueError('Direção inválida')
    if data['risk_state'] not in ('safe','near_limit','reduce'):raise ValueError('Risco inválido')
    if type(data['toxic_flow']) is not bool:raise ValueError('Fluxo desconhecido ou inválido')
    numeric(data['setup_quality'],0,3);numeric(data['confidence'],0,1)
    probabilities=data['probabilities'];fields(probabilities,('long','short','neutral'))
    for value in probabilities.values():numeric(value,0,1)
    if not math.isclose(sum(probabilities.values()),1,abs_tol=1e-8):raise ValueError('Probabilidades não somam um')
    selected=probabilities[data['direction']]
    if selected!=max(probabilities.values()):raise ValueError('Escolha inconsistente')
    confidence=(selected-1/3)/(1-1/3)
    if not math.isclose(data['confidence'],confidence,abs_tol=1e-8):raise ValueError('Confiança inconsistente')
    if not all(isinstance(data[k],str) and 0<len(data[k])<=80 for k in ('model','schema')):raise ValueError('Versão obrigatória')
    return {**data,'probabilities':dict(probabilities)}
