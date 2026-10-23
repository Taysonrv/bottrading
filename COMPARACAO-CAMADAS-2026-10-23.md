# Comparação exploratória EMA/ATR × cinco camadas — 23/10/2026

**Veredito: sem aprovação.** O candidato perdeu nas quatro janelas com custos base e também nas quatro com custos dobrados. Não demonstrou vantagem líquida neste modelo. Não será promovido ao motor ativo.

Foram baixados e validados 70.176 candles públicos BTC/USDT 15m, cobrindo 731 dias. Cada janela usa 600 candles anteriores de aquecimento e reinicia o capital fictício em 20 USDT. As janelas não formam uma carteira contínua e seus retornos não devem ser compostos ou somados.

| Regra | Custos | Início UTC | Fim UTC | Retorno líquido | Comprar/manter | DD máximo | Ciclos |
|---|---|---|---|---|---|---|---|
| ema_atr | base | 2024-10-28 | 2025-04-27 | -8.45% | 36.84% | 10.00% | 94 |
| layered_v1 | base | 2024-10-28 | 2025-04-27 | -8.45% | 36.84% | 10.00% | 92 |
| ema_atr | double_costs | 2024-10-28 | 2025-04-27 | -9.05% | 36.29% | 10.00% | 58 |
| layered_v1 | double_costs | 2024-10-28 | 2025-04-27 | -9.05% | 36.29% | 10.00% | 59 |
| ema_atr | base | 2025-04-27 | 2025-10-25 | -7.64% | 18.12% | 8.38% | 104 |
| layered_v1 | base | 2025-04-27 | 2025-10-25 | -7.50% | 18.12% | 8.24% | 102 |
| ema_atr | double_costs | 2025-04-27 | 2025-10-25 | -10.00% | 17.65% | 10.00% | 98 |
| layered_v1 | double_costs | 2025-04-27 | 2025-10-25 | -10.00% | 17.65% | 10.00% | 97 |
| ema_atr | base | 2025-10-25 | 2026-04-24 | -9.78% | -30.93% | 10.00% | 59 |
| layered_v1 | base | 2025-10-25 | 2026-04-24 | -9.78% | -30.93% | 10.00% | 61 |
| ema_atr | double_costs | 2025-10-25 | 2026-04-24 | -9.89% | -31.20% | 10.00% | 54 |
| layered_v1 | double_costs | 2025-10-25 | 2026-04-24 | -9.89% | -31.20% | 10.00% | 51 |
| ema_atr | base | 2026-04-24 | 2026-10-23 | -9.58% | 5.53% | 10.00% | 73 |
| layered_v1 | base | 2026-04-24 | 2026-10-23 | -9.58% | 5.53% | 10.00% | 71 |
| ema_atr | double_costs | 2026-04-24 | 2026-10-23 | -9.69% | 5.11% | 10.00% | 73 |
| layered_v1 | double_costs | 2026-04-24 | 2026-10-23 | -9.69% | 5.11% | 10.00% | 71 |

## Como reproduzir

```powershell
python -m spot_engine.data --help
python -m spot_engine.layered_comparison --csv CAMINHO_DO_CSV_VALIDADO.csv --windows 4
python -m unittest tests.test_layered_comparison tests.test_layered_research tests.test_spot_backtest -v
```

O CSV exige o manifesto gerado pelo coletor. O relatório JSON fica em reports/local/layered-comparison com hash do CSV, hashes das fontes, configurações e todas as janelas/custos. Os dados locais brutos não são publicados neste commit.

## Método e limitações

São duas regras fixas × dois cenários de custo = quatro configurações examinadas neste comparativo, além de qualquer pesquisa anterior. Não houve otimização. Isto é uma auditoria cronológica exploratória, **não** treinamento walk-forward ou holdout comprovadamente inédito.

Os sinais são calculados progressivamente em candles fechados; a entrada é simulada apenas na abertura seguinte. O filtro de camadas só pode suprimir entradas EMA existentes. Saídas e custos seguem o mesmo simulador nas duas regras. Em candle que toca stop e alvo, o stop tem prioridade. Não se escolhem apenas janelas favoráveis.

Custos base: taxa 0,1% por lado e slippage 0,1% por lado; estresse: ambos dobrados. São hipóteses, não a comissão específica de uma conta. A posição tem teto de 6 USDT, stop 2%, alvo 4%, limite de risco previsto de 1%, perda diária de 3% e DD de 10%. A aritmética deste modelo é float de pesquisa, distinta do ledger decimal.

Os filtros históricos de lote/notional, spread, book, fila de ordens limite, preenchimentos parciais e latência não foram reconstruídos. Frações podem ser inexequíveis com 20 USDT. O modelo usa saída a mercado sintética e não reproduz o mecanismo LIMIT da sessão atual. Os limites observam aberturas/fechamentos e não toda a trajetória intrabar. O teste é de um único par; não reproduz a escolha multipar nem autoriza uma carteira compartilhada.

Acerto e Sharpe são métricas descritivas sem garantia de significância. Não foram produzidos intervalos de confiança ou bootstrap. As perdas observadas são motivo suficiente para rejeitar a promoção agora; não provam que toda estratégia de tendência seja inviável.

Próximo trabalho de pesquisa: auditar custos/exequibilidade e a hipótese econômica antes de criar outra variante. Registrar cada nova tentativa e manter o holdout reservado; não procurar parâmetros até este histórico ficar positivo.

## Integridade

CSV SHA-256: `ac28586afb033cf4788fd73185eb6968287fa8227a5dbad1bb8993bbbca10b5b`

- config.py: `d7473a010f15e93d9a90d4a907e99eb48a8d90200b16355898a150b66ab36f5a`
- strategy.py: `8b59a3c1e3a1614e4d0776072451c308844c6d06c2312fa20b589a3754cf521e`
- data.py: `436d2b59ec90f2f142cdbca6b71f8a84ec665e203a6a525cc2ff1437ae676889`
- backtest.py: `83a2b902bd7430cef002a99e25889f3c597a97d93b29b99f48c9a921146bbcca`
- layered_research.py: `4f8312ddad4378906d3f0255294e9d28d006c9e67b884f45454a4fbf74e2a4fc`
- layered_comparison.py: `54de52142982c4ed26180b0d433b5d9e03167b9abc6af8b146f74e72c9d41c65`
- temporal_validation.py: `cb40495b8dbdf3332e9d191ccd75874922fbc4989ba60b988dff6a02f0914b27`
