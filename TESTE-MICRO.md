# Pesquisa de pequenas compras e vendas

Execute `python micro_research.py`. Usa BTCUSDT e ETHUSDT, candles públicos de um minuto, 60 minutos de aquecimento e 12 horas de avaliação. Capital fictício de 1.000 USDT compartilhado; compras de até 25 USDT incluindo custos.

Compara margens líquidas fixas de 0,25%, 0,50% e 1%, com custos normais e dobrados. Sinais usam candles fechados e execução aproximada na abertura seguinte. Não reproduz livro, fila ou todos os filtros da corretora.

Compra recuos de 0,1% abaixo da média de 20 minutos se ela estiver acima da média de 60. Compras adicionais exigem novo recuo de 0,3%. Vende pelo alvo líquido, tendência de queda ou perda líquida de 2% do lote. Gaps podem causar perdas mesmo após sinal de lucro.

STOP é verificado antes de cada ordem. Drawdown de 15% bloqueia operações; não garante liquidação. Limites de posição permanecem em 20% por ativo e 60% no conjunto. Resíduos abaixo do mínimo de 10 USDT ficam na carteira simulada.

Resultados ficam em `reports/local/micro-results.json` e `.md`, ignorados pelo Git e exibidos no painel como pesquisa não ativa. Uma janela curta já consultada não valida estratégia nem escolhe uma vencedora. Não altera a simulação noturna ou envia ordens à Binance.
