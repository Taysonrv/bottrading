# Aceitação do simulador de ordens limitadas

**Dados e preços inteiramente artificiais. Não é backtest, previsão de lucro ou aprovação de estratégia.**
Cada cenário começa com patrimônio fictício de 1.000 USDT; o cenário de queda começa com 800 em caixa e 200 em ativo.

| Cenário artificial | Patrimônio marcado | Taxas pagas | Saldo reservado | Execuções parciais/totais | Ordens abertas |
|---|---:|---:|---:|---:|---:|
| synthetic_roundtrip_and_replacement | 1002.45000 | 0.05000 | 23.77375 | 6 | 1 |
| synthetic_partial_then_cancel | 999.89050 | 0.00950 | 0.00000 | 1 | 0 |
| synthetic_stop_before_fill | 1000.00000 | 0.00000 | 0.00000 | 0 | 0 |
| synthetic_crash_with_existing_inventory | 820.00000 | 0.00000 | 0.00000 | 0 | 0 |

Patrimônio marcado inclui posições ao último preço artificial, sem custo estimado de liquidação. Taxas cobradas em USDT neste modelo.
Cenário positivo foi construído para testar compra/venda; não demonstra lucratividade. Reposição permanece pendente e não usa o evento anterior.
Na queda artificial, drawdown alcança 18%: a trava cancela ordens, mas não liquida ativos nem limita a perda a 15%.
Participação máxima de 10% do volume agressor informado; não estima posição real na fila. Toque de preço não preenche.
Filtros de preço/lote/mínimo são fictícios. Fonte técnica de referência: https://developers.binance.com/en/docs/products/spot/filters
