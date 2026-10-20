# Estratégias solicitadas: comparação isolada

`python spot_strategy_suite.py` compara quatro hipóteses em 30 dias de candles horários, mais 60 horas de aquecimento. Cada cenário recebe seus próprios 20 USDT fictícios; não são somados ao saldo real ou ao experimento contínuo. Custos 1x: taxa/slippage de 0,1% cada por lado; 2x dobra ambos. Universo fixo BTCUSDT, ETHUSDT, DOGEUSDT e PEPEUSDT, filtros atuais. Sem spread histórico observado e sem reconstrução histórica dos filtros. Sinal usa fechamento anterior, preenchimento aproximado na abertura seguinte.

- Grid Spot: proxy de inventário, quatro degraus de queda de 0,5% em torno da âncora fixa. Ajusta exposição, vende ao ganho líquido de 1%, desativa o episódio se sair da faixa de ±3%. Não simula ordens limitadas pendentes, fila ou fills intrabar; não equivale ao Grid nativo Binance. O simulador de ordens limitadas anterior permanece separado.
- DCA Spot: compras a cada 24 horas, mesmo valor orçamentado, sem martingale e sem venda programada. Não equivale a prometer realização de lucro diário.
- Rebalanceamento: 15% para cada um dos quatro ativos e 40% em caixa; avalia a cada 24 horas, com tolerância de 5 pontos percentuais. Cada ordem respeita o mínimo; mínimos podem impedir a alocação planejada.
- Souto: adaptação do estudo de 2023. Compra quando preço está no primeiro quartil dos últimos 26 e média16 < média10 < média26. Vende no quarto quartil e média16 > média10 > média26. Quartis inclusivos definidos explicitamente. O estudo usa sequência de preços e BNB/BRL; aqui são candles horários em quatro pares USDT, portanto não é reprodução literal ou validação do retorno publicado.

Limites da pesquisa: até 5 USDT por ordem incluindo custos de compra, 25% por ativo e 60% total. Drawdown de 15% e STOP bloqueiam novas ordens, não garantem liquidação. Mantém resíduos; carteira final marca saída estimada mesmo que exista mínimo que impeça executá-la. Registra compras, vendas, bloqueios, taxas e posições remanescentes. Não há reinvestimento irrestrito, alavancagem, futuros ou funding arbitrage.

Resultados em reports/local/spot-suite.json, ignorados pelo Git e exibidos na aba Estratégias. Positivo em janela já consultada não comprova superioridade fora da amostra. Nenhuma seleção automática ou mudança na estratégia da posição atual. Uma sessão futura por estratégia precisaria ser independente e identificada desde o início.

Referências:
- Binance Academy: https://www.binance.com/pt-BR/academy/articles/your-guide-to-binance-trading-bots
- Thomaz Machado Souto, Explorando o potencial do mercado de criptoativos: desenvolvimento de um robô de negociação na Binance, UFVJM, 2023. Regras na página impressa 39, folha 41 do PDF fornecido. Tabela mensal na página impressa 45 não basta para auditar rentabilidade líquida e capitalização; não importar seu total como expectativa do nosso bot.
