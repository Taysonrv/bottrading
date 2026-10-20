# Triagem das seis referências fornecidas

Estas referências são fontes de hipóteses, não autorização de execução, prova de retorno ou instruções a seguir automaticamente. Não importamos código, credenciais ou recomendações de ativos das páginas. A sessão contínua e o plano prospectivo anterior não são alterados.

| Fonte | Leitura e adoção |
|---|---|
| Bitso | RSI, médias, volume e Bollinger já cobertos. Delta de agressão em USDT adicionado à exibição da janela WebSocket. MVRV e valor justo ByteTree ficam pendentes de fonte on-chain, licença, histórico e regra explícita; não inferidos de candles. |
| Gate | O URL exato fornecido não abriu na ferramenta de pesquisa e retornou HTTP 403 na consulta direta. Não atribuímos regras ao conteúdo inacessível. Outros resultados Gate encontrados não são tratados como a mesma página. |
| Empiricus | Página comercial descreve sistema proprietário e potencial de valorização de até 270 vezes, sem regras públicas reproduzíveis. Não adotado como algoritmo, alvo ou expectativa de retorno. Nenhuma inscrição ou compra realizada. |
| CriptoFácil | Gestão de risco, diário, médias/RSI/MACD já presentes. Acrescentada hipótese de Estocástico com regras explicitadas abaixo. Estatísticas, taxas e mínimos citados não substituem exchangeInfo e custos observados da nossa plataforma. |
| Switch Markets | Consulta direta permitiu leitura. Adicionadas adaptações horárias de EMA9/20, ribbon5/8/13 e squeeze. ORB exige definir sessão em cripto 24/7 e resolução menor; Fibonacci exige algoritmo causal de swings; Level2 exige snapshot/diff-depth sincronizados. Permanecem não implementados, sem alegar que bookTicker é profundidade completa. |
| Strike.money | Catálogo amplo de estilos de trading em vários mercados, não 70 algoritmos executáveis prontos. DCA, tendência, range, rompimento e rebalanceamento mapeados aos testes existentes. Opções, futuros, short selling, ações/dividendos e outros instrumentos não são habilitados no bot Spot. |

## Quatro hipóteses novas (adaptações, não reprodução literal)

- EMA9/20 com tendência EMA20>EMA50, preço>EMA50 e RSI14>50 no cruzamento ascendente. Saída abaixo do cruzamento. Não usa dois timeframes como a sugestão da Switch; a adaptação é de um único timeframe horário.
- Ribbon EMA5/8/13: EMA5 passa de posição abaixo/igual à maior das outras duas para EMA5>EMA8>EMA13, com preço acima de EMA5 e filtro de tendência. Saída EMA5 abaixo das duas. Não implementa trailing stop na EMA13.
- Squeeze Bollinger20, dois desvios populacionais: largura das cinco janelas anteriores ≤2%; fechamento acima da banda superior, largura cresce mais de 10% em relação à anterior, volume ≥1,5x média anterior de 20 e filtro de tendência. Sai abaixo da média20. Limiares são hipóteses declaradas pelo projeto, não números comprovados pela fonte.
- Estocástico14: %K sai de abaixo de 20 e cruza acima da média %D3, com filtro de tendência. Saída %K>80 ou %K<%D. Flat recebe 50. Regras de entrada/saída escolhidas para pesquisa, não prescritas de forma completa pelo artigo.

Todas usam a infraestrutura da comparação Spot: 20 USDT por carteira histórica, custos normais/dobrados, saídas protetivas comuns, mínimos reais atuais e limites. O laboratório passa de 13 para 17 hipóteses (34 cenários). As quatro regras novas ainda não foram inscritas em validação prospectiva; não inserir retroativamente no plano existente. Não selecionar vencedora após repetir janelas semelhantes.

## Agressão

No painel, delta da janela = notional total × (2×fração compradora−1). É apenas soma assinada dos aggTrades observados nos últimos até 60 segundos. Não é CVD de sessão ou histórico completo. Reset por lacuna/reconexão e aquecimento continuam em vigor. Não determina sozinho direção futura nem identifica participantes institucionais.

Fontes fornecidas:
- https://bitso.com/br/blog/melhores-indicadores-criptomoedas/
- https://www.gate.com/pt-br/learn/articles/top-crypto-day-trading-strategies
- https://www.empiricus.com.br/artigos/investimentos/o-melhor-trader-do-mundo-conheca-estrategia-que-busca-criptomoedas-que-podem-valorizar-ate-270-vezes-lbrdjm045/
- https://www.criptofacil.com/investimento-criptomoedas/sucesso-day-trading/
- https://www.switchmarkets.com/pt/aprenda/6-estrategias-avancadas-de-analise-tecnica-para-operar-com-mais-inteligencia
- https://www.strike.money/stock-market/trading-strategies
