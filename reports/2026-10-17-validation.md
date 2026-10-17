# Comparação histórica — simulação

Estratégia configurada: `regime_v1`. Nenhuma seleção automática.

| Estratégia | Ativo/carteira | Retorno final | Comprar e manter | Drawdown | Aprovada |
|---|---|---:|---:|---:|---|
| regime_v1 | BTCUSDT | 0.77% | 23.22% | 2.48% | Não |
| regime_v1 | ETHUSDT | 0.27% | 24.32% | 3.99% | Não |
| regime_v1 | Carteira | 1.03% | 23.77% | 6.01% | Não |
| regime_v1 | Carteira com posições iniciais (80%) | 0.75% | 23.77% | 6.01% | Não |
| regime_v1 | Carteira contínua (período completo) | -11.82% | -33.72% | 16.02% | Não |
| trend_v1 | BTCUSDT | 0.97% | 23.22% | 2.71% | Não |
| trend_v1 | ETHUSDT | -0.79% | 24.32% | 3.97% | Não |
| trend_v1 | Carteira | 0.13% | 23.77% | 6.41% | Não |
| trend_v1 | Carteira com posições iniciais (80%) | -0.13% | 23.77% | 6.41% | Não |
| trend_v1 | Carteira contínua (período completo) | -8.52% | -33.72% | 22.80% | Não |
| breakout_v1 | BTCUSDT | 0.05% | 23.22% | 1.40% | Não |
| breakout_v1 | ETHUSDT | 0.11% | 24.32% | 1.98% | Não |
| breakout_v1 | Carteira | 0.17% | 23.77% | 2.85% | Não |
| breakout_v1 | Carteira com posições iniciais (80%) | -0.01% | 23.77% | 2.85% | Não |
| breakout_v1 | Carteira contínua (período completo) | -10.90% | -33.72% | 15.10% | Não |

Tabela: período final reservado (25% após aquecimento), exceto a linha contínua que usa todo o período. Aprovação exige também passar nas três janelas anteriores, com custos dobrados, com posições iniciais e sem reiniciar a carteira ao longo do período completo.

O cenário de posições iniciais assume 80% do capital já investido, com pesos iguais pelo preço de abertura. Não representa a carteira real nem inclui seu custo histórico. A redução de exposição continua limitada por ordem; não é instantânea.

Benchmark principal: comprar e manter com 100% do capital (pesos iguais na carteira). O JSON também mostra benchmark proporcional à exposição.

Regras e parâmetros fixos; não houve otimização. Reutilizar este período para ajustar regras transforma-o em desenvolvimento; será necessário um novo período futuro para confirmar.

Execução histórica: abertura seguinte ao sinal, taxas/slippage estimados, limites compartilhados e avaliação conservadora das mínimas horárias. Não modela livro completo nem garante perdas limitadas a 15%.


Consulta concluída em 2026-10-17T22:03:55.032044+00:00. Histórico: 365 dias de candles horários públicos.

Identificador do código/configuração: `de3ed5b450dc1d74d9450819570250682014d44c1afce53fff6d4bffe1bf8d19`.

O bloqueio de drawdown impede novas ordens, inclusive vendas. Posições remanescentes continuam expostas; por isso o teste contínuo pode ultrapassar 15%. Nenhuma estratégia foi aprovada. Este relatório não contém saldos reais da conta.
