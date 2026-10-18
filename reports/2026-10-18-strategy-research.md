# Pesquisa de estratégias — Binance Spot

Consulta em 18/10/2026. Este documento define prioridades de pesquisa; não aprova estratégias nem altera o motor ativo. Não foi realizado novo backtest nesta pesquisa.

## Conclusão

Primeira candidata: tendência de médio prazo, comprada ou em caixa, com exposição limitada e ajustada à volatilidade. A prioridade é uma interpretação da literatura e das restrições deste projeto, não uma comprovação de superioridade. Nenhuma estratégia atual está aprovada para dinheiro real.

| Prioridade | Família | Uso proposto | Limitação |
|---|---|---|---|
| 1 | Tendência temporal | BTC/ETH, comprar quando o próprio histórico indica tendência positiva; caixa quando negativa | Sinais falsos e atraso em reversões; evidência histórica não garante vantagem futura |
| 2 | Rompimento com filtro de tendência | Comprar superação de máxima anterior, sem usar a vela futura | Variante de tendência, não fonte independente de diversificação; sensível a custos |
| 3 | Momentum relativo | Selecionar ativos líquidos mais fortes, somente comprados e com filtro absoluto | Estudos com posições vendidas não representam Spot; exige universo histórico sem viés de sobrevivência |
| 4 | Reversão à média / grid | Pesquisa posterior, condicionada a lateralização | Lucro de operações fechadas pode ocultar perda no estoque; queda persistente e taxas precisam entrar no resultado |

Dimensionamento por volatilidade é uma camada de risco, não uma estratégia de previsão. Nesta aplicação nunca deve elevar exposição acima dos limites existentes ou introduzir alavancagem. Manter USDT também tem riscos próprios e não equivale a caixa bancário sem risco.

## Evidência e alcance

- Liu e Tsyvinski encontram momentum temporal em criptomoedas na amostra estudada. O comportamento varia entre ativos e horizontes: não justifica aplicar um único indicador a todas as moedas. [Risks and Returns of Cryptocurrency, NBER](https://www.nber.org/papers/w24877.pdf).
- Liu, Tsyvinski e Wu documentam fatores de mercado, tamanho e momentum na seção transversal. Carteiras long-short do estudo não podem ser tratadas como retornos realizáveis de um bot Spot comprado. [Common Risk Factors in Cryptocurrency](https://www.nber.org/papers/w25882).
- Moreira e Muir estudam redução de risco em períodos de maior volatilidade e melhor desempenho ajustado ao risco em fatores de ações e moedas. É evidência para investigar a camada de risco; não valida sua transferência para cripto. [Volatility-Managed Portfolios](https://amoreira2.github.io/alan-moreira.github.io/VolPortfolios_published.pdf).
- Rozario e coautores apresentam resultados históricos de tendência em cripto. É um preprint de 2020; os retornos publicados não são uma previsão para este bot, seus custos ou seus limites. [A Decade of Evidence of Trend Following Investing in Cryptocurrencies](https://arxiv.org/abs/2009.12155).
- A documentação da Binance separa resultados das operações de grid do resultado das posições abertas. Avaliar patrimônio total é essencial. [Spot Grid](https://www.binance.com/en-PH/support/faq/detail/688ff6ff08734848915de76a07b953dd).
- Testar muitas alternativas e escolher a vencedora pode gerar sobreajuste. Registrar tentativas, inclusive fracassos, é parte da pesquisa. [The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).

## Relação com o bot existente

`research.py` trabalha com candles horários. As médias de 48 e 200 observações de `trend_v1` representam horas, não dias. Seu resultado negativo não testa nem refuta diretamente uma regra diária de vários meses.

O relatório `2026-10-18-defensive.md` permanece válido: nenhuma regra foi aprovada. O gatilho de drawdown de 15% não garante que a perda máxima se limite a 15%; gaps, custos e redução gradual podem ultrapassá-lo.

## Próximo experimento proposto, antes de observar resultados

Implementar depois, separadamente do motor ativo, apenas três hipóteses iniciais em candles diários fechados:

1. Tendência: fechamento acima da média simples de 200 dias.
2. Momentum absoluto: retorno de 90 dias positivo.
3. Rompimento: entrada acima da máxima dos 55 dias anteriores; saída abaixo da mínima dos 20 dias anteriores.

Os períodos são escolhas de pesquisa declaradas, não parâmetros ótimos extraídos dos artigos. Comparar cada hipótese com e sem ajuste de volatilidade de 30 dias; registrar as seis tentativas. Para a variante ajustada, usar multiplicador limitado a 1, alvo anual de 20% e anualização de 365 dias. O alvo é experimental e não garante volatilidade realizada de 20%. O peso-base continua limitado pela configuração do bot. Sem retocar períodos após consultar o teste.

Usar BTCUSDT e ETHUSDT inicialmente; pelo menos cinco anos, se íntegros e disponíveis, incluindo aquecimento de 200 dias antes da avaliação. Sinais somente após fechamento; execução na abertura seguinte, com limites reais de ordem, saldo, taxas, spread e slippage. Não simular saída ilimitada se o motor só pode reduzir gradualmente.

Dividir cronologicamente: primeiros 60% desenvolvimento, próximos 20% avaliação em janelas, últimos 20% teste final congelado. O último ano já consultado pelo projeto não volta a ser chamado de amostra intocada: uma nova divisão não apaga esse conhecimento. A confirmação independente exige observação futura após congelar código e configuração.

Comparar resultado líquido com comprar e manter BTC, ETH, carteira 50/50 e uma referência com a mesma exposição inicial em cripto e caixa. Mostrar retorno, drawdown, volatilidade, giro, custos, tempo em caixa e resultados por período. Simular também carteira inicialmente investida e custos dobrados.

Preservar os critérios atuais de aprovação; registrar qualquer reprovação, inclusive retorno inferior ao benchmark ou drawdown acima do limite. Não mudar o benchmark para fazer uma candidata passar. Ganhar no retorno ajustado ao risco, isoladamente, não satisfaz a exigência do usuário de superar o mercado.

Não incluir Earn, vendas reais, novos ativos, arbitragem com futuros ou implantação automática. Revisar o resultado com o usuário antes de adotar qualquer alteração na estratégia ativa.
