# Comparação prospectiva de frequência

`python prospective_research.py` registra no primeiro uso uma janela que começa na próxima hora UTC, o universo e filtros observados e um hash do código. Usos posteriores preservam esse plano; mudança de código bloqueia a comparação. Não reinicia carteira antiga nem executa operações reais.

Capital fictício de 20 USDT, até 25% (máximo 5 USDT incluindo custos) por entrada, uma posição de cada vez. Compara entrada horária e entrada a cada 24 horas relativas ao início do plano; as saídas continuam verificadas a cada candle horário em ambas. Mesma regra de tendência/recuo e proteção da pesquisa anterior. Custos normais e dobrados. Sem aumento de posição para alcançar o mínimo.

Somente após 48 horas futuras fechadas calcula resultados parciais, por até 168 horas, com 60 horas anteriores exclusivamente para aquecimento. Os filtros e universo são congelados na inscrição, mas novas exclusões por dados incompletos são informadas. Isso não elimina todos os vieses ou valida a corretora; filtros podem mudar durante a janela.

Consultas são manuais: repita o comando para atualizar. Não há processo de coleta contínua ou promessa de acompanhamento automático. A comparação usa candles, taxas e slippage aproximados; não reproduz spread/livro real. Não produz aprovação automática, nem mesmo com resultado positivo. Arquivos ficam em reports/local, ignorados pelo Git.

# Auditoria da sessão anterior

A sessão antiga teve última medição salva às 00:59 de 19/10/2026 (Brasília), sem registro de encerramento ou exceção. O PID original não estava ativo quando verificado. A causa externa não é demonstrável pelos logs disponíveis. Não reconstruir os preços ausentes como se fossem observação ao vivo; não chamar a última medição de fechamento completo da noite. Preservar saldos e relatórios anteriores.

# Limitação da recompra Solana

Erro Jupiter Swap 6024: saldo insuficiente para a troca, taxas ou aluguel. Simulações independentes não transferem o saldo USDC entre as etapas. Validar o ciclo exige estado encadeado em ambiente de simulação/fork ou uma transação atômica construída e auditada. Este projeto ainda não implementa isso; nenhuma falha é tratada como aprovação e não se financia a carteira para contornar a limitação.

Fonte: https://developers.jup.ag/docs/swap/v1/common-errors
