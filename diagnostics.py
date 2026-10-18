"""Explain actual simulation/observation gates without changing them."""


def assess(*, config_ok, stop, halted, validation_exists, validation_current,
           validation_passed, observation_exists, observation_current,
           activity_recent, performance_exists):
    checks = []
    def add(code, title, status, detail, next_step):
        checks.append({'code': code, 'title': title, 'status': status, 'detail': detail, 'next_step': next_step})
    add('config', 'Configuração', 'ok' if config_ok else 'blocked',
        'Modo de simulação e limites válidos.' if config_ok else 'Configuração ausente ou inválida.',
        'Nenhuma ação necessária.' if config_ok else 'Revise config.json no computador antes de iniciar o processo.')
    add('stop', 'Botão de emergência', 'blocked' if stop else 'ok',
        'STOP está acionado e impede também a observação.' if stop else 'STOP não está acionado.',
        'Revise o motivo da parada. A retomada deve ser feita pelo terminal.' if stop else 'O botão de desligar permanece disponível no painel.')
    add('drawdown', 'Proteção de drawdown', 'blocked' if halted else 'ok',
        'A carteira simulada está com a trava de risco acionada.' if halted else 'Nenhuma trava de drawdown registrada.',
        'Revise a exposição e o histórico; não reinicie os saldos para remover perdas.' if halted else 'A ausência de trava não significa que a estratégia está aprovada.')
    if not validation_exists:
        detail, step = 'Não há relatório de validação.', 'Execute a validação histórica pelo terminal.'
    elif not validation_current:
        detail, step = 'O relatório venceu ou pertence a outra versão do código/configuração.', 'Gere uma nova validação; o painel não reaproveita aprovações antigas.'
    elif not validation_passed:
        detail, step = 'A estratégia ativa reprovou nos critérios históricos.', 'Revise os resultados na aba Estratégias. Não remova a trava para forçar operações.'
    else:
        detail, step = 'A aprovação histórica está vigente para esta versão.', 'Isso permite apenas a simulação, desde que as demais travas estejam liberadas.'
    add('validation', 'Validação da estratégia', 'ok' if validation_current and validation_passed else 'blocked', detail, step)
    if observation_exists and not observation_current:
        detail, status, step = 'A sessão de observação pertence a outra versão.', 'blocked', 'Encerre o observador e arquive a sessão antiga antes de iniciar uma nova.'
    elif observation_exists:
        detail, status, step = 'A sessão pertence à versão atual.', 'ok', 'Mantenha o observador ativo para registrar as próximas amostras.'
    else:
        detail, status, step = 'Ainda não há sessão de observação.', 'info', 'Inicie a observação pelo terminal. O painel não inicia processos.'
    add('observation', 'Sessão de observação', status, detail, step)
    add('activity', 'Atividade do processo', 'ok' if activity_recent else 'attention',
        'O bot enviou um sinal de atividade recentemente.' if activity_recent else 'Nenhum sinal de atividade recente foi recebido.',
        'Esse sinal não comprova execução saudável; confira os eventos.' if activity_recent else 'Confira se o processo está aberto e usando a mesma pasta de dados do painel.')
    add('performance', 'Medição da carteira', 'ok' if performance_exists else 'info',
        'Há uma medição salva; confira a data na visão geral.' if performance_exists else 'Ainda não há medição de patrimônio.',
        'A data do painel não atualiza o preço de uma medição antiga.' if performance_exists else 'Um ciclo de simulação atualiza a medição, mesmo quando as operações são bloqueadas.')
    return {'paper_ready': config_ok and not stop and not halted and validation_current and validation_passed,
            'observation_ready': config_ok and not stop and (not observation_exists or observation_current),
            'checks': checks, 'note': 'Diagnóstico do estado salvo. Não autoriza operações reais nem inicia processos.'}
