# Adoção das referências no laboratório, não em execução real

Execute `python spot_strategy_suite.py`. As 13 hipóteses abaixo usam carteiras históricas separadas de 20 USDT, quatro pares fixos e custos normais/dobrados. Não muda a posição ou código da sessão live_small_paper. Não realiza votação de indicadores, otimização de parâmetros ou escolha automática do melhor retorno. Positivo não significa aprovação; múltiplas tentativas aumentam risco de seleção oportunista.

## Hipóteses implementadas

1. Grid Spot: proxy de inventário já documentado; não é grade de ordens limitadas executáveis.
2. DCA Spot: compras periódicas de 24 horas, sem martingale.
3. Rebalanceamento: 15% por ativo, 40% em caixa, tolerância de 5 pontos percentuais.
4. Quartis Souto: médias 10/16/26 e quartis inclusivos, adaptação horária do PDF.
5. Cruzamento EMA9/EMA21: compra no cruzamento para cima com EMA20>EMA50 e preço>EMA50; saída pelo cruzamento oposto.
6. Rompimento: fechamento acima das máximas das 20 barras anteriores, volume ≥1,5x média anterior de 20 e filtro de tendência. Saída abaixo das mínimas anteriores de 10.
7. Pullback referência: EMA20>EMA50, preço acima de EMA50 e até 0,5% acima de EMA20, retorno positivo em seis horas.
8. Pullback com RSI: mesma entrada, restringindo RSI Wilder14 a [40,65].
9. Pullback com ATR: mesma entrada, distância fixa na compra de 2×ATR14; stop abaixo do preço preenchido e alvo a duas vezes a distância acima. ATR é média simples dos últimos 14 true ranges, não Wilder. Compra dimensionada para perda planejada de até 0,5% da carteira, incluindo aproximação de custos, e limitada a 5 USDT. Gaps, mínimos e slippage podem exceder o risco planejado. Não recalcula stop de posição existente. Também sai por perda de tendência.
10. Reversão: eficiência direcional de 20 barras <0,3, preço abaixo da banda média20−2 desvios populacionais e RSI14<30. Sai na média20 ou eficiência ≥0,6. É proxy explícito de regime lateral, não detector infalível.
11. VWAP móvel: preço cruza para cima o VWAP das últimas 20 barras com filtro de tendência. Usa preço típico × volume base; não é VWAP de sessão/tick nem perfil de volume. Sai abaixo do VWAP.
12. Momentum: retorno de seis horas ≥1%, volume ≥2x média anterior de 20 e tendência confirmada. Sai abaixo de EMA20 ou momentum negativo em três horas.
13. MACD12/26/9: compra no cruzamento ascendente do histograma, com filtro de tendência; vende no cruzamento descendente.

Para hipóteses técnicas, exceto ATR, também há saída por perda líquida estimada de 2% ou ganho de 1%. Não faz preço médio adicional nas hipóteses técnicas. Usa somente candles fechados para sinais e abertura seguinte para preencher. EMAs e RSI são recalculados na janela móvel de 60 barras; não representam um histórico infinito. Fees/slippage de 0,1% cada por lado, dobrados no stress. Sem spread histórico e sem reconstrução histórica dos filtros; resultados são pesquisa exploratória. Não são bots nativos Binance.

## Referências sem regra completa ou fora do escopo

- Multi-Sniper/fluxo: coletor WebSocket observa e informa hipóteses de pressão, sem gerar ordens. IOC parcial e profundidade completa ainda não implementados.
- Notícias/sentimento: não adotados como gatilho automático; faltam fontes, horários e regras objetivas reproduzíveis.
- HFT/scalping: não implementados como execução validada; custos, latência e fills precisam de estudo próprio. O teste anterior de pequenos ciclos continua separado.
- Arbitragem entre exchanges: não implementada; requer dados sincronizados, saldos e custos de duas plataformas.
- Futuros, funding arbitrage, shorts, CFDs e opções: excluídos do escopo aprovado Spot sem alavancagem.
- Telegram: módulo existente separado; estas mudanças não afirmam envio de notificações no experimento contínuo.

O arquivo privado reports/local/spot-suite.json guarda as comparações. A aba Estratégias mostra os resultados salvos; não é execução contínua das 13 carteiras. A carteira contínua original permanece independente. A pesquisa prospectiva anterior também não recebe estas novas hipóteses retroativamente.
