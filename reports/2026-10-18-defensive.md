# Saída defensiva — experimento histórico

Pesquisa separada: nenhuma mudança no bot ativo ou nos critérios de aprovação.

| Estratégia | Cenário contínuo | Retorno | Drawdown | Vendas defensivas | Exposição final (USDT) |
|---|---|---:|---:|---:|---:|
| regime_v1 | Bloqueio atual | -11.27% | 16.56% | 0 | 156.10 |
| regime_v1 | Saída gradual | -14.30% | 15.07% | 3 | 0.00 |
| regime_v1 | Saída gradual / custos dobrados | -14.36% | 15.02% | 3 | 0.00 |
| regime_v1 | 80% investido / bloqueio atual | -11.60% | 16.02% | 0 | 103.84 |
| regime_v1 | 80% investido / saída gradual | -13.62% | 15.01% | 2 | 0.00 |
| trend_v1 | Bloqueio atual | -9.10% | 22.74% | 0 | 393.80 |
| trend_v1 | Saída gradual | -14.22% | 15.02% | 8 | 0.13 |
| trend_v1 | Saída gradual / custos dobrados | -14.63% | 15.29% | 5 | 0.00 |
| trend_v1 | 80% investido / bloqueio atual | -8.42% | 22.77% | 0 | 396.73 |
| trend_v1 | 80% investido / saída gradual | -13.59% | 15.05% | 8 | 0.13 |
| breakout_v1 | Bloqueio atual | -11.08% | 15.10% | 0 | 161.98 |
| breakout_v1 | Saída gradual | -14.51% | 15.03% | 3 | 0.00 |
| breakout_v1 | Saída gradual / custos dobrados | -14.45% | 15.02% | 2 | 1.51 |
| breakout_v1 | 80% investido / bloqueio atual | -10.17% | 15.08% | 0 | 164.32 |
| breakout_v1 | 80% investido / saída gradual | -13.69% | 15.04% | 3 | 0.00 |

Mesmo histórico e regras de entrada para as políticas comparadas. O cenário experimental só vende após o gatilho de 15%; não volta a comprar.
Vendas simuladas continuam limitadas por ordem e ocorrem na abertura seguinte à detecção. Lacunas de preço, custos e o tempo para reduzir posições podem fazer o drawdown ultrapassar 15%.
STOP sempre prevalece. Não se assume liquidação instantânea. Resíduos abaixo do mínimo de ordem podem permanecer.
Um resultado melhor neste histórico não valida a política em dados futuros. Nenhuma estratégia foi liberada por esse experimento.


Consulta: 2026-10-18T13:21:28.159366+00:00. Dados públicos, 365 dias de candles horários.

Código/configuração: `0643c8256a0282288bc5e6d6b3be465062189f072226f4c4a8fe9cebbf179c14`.
