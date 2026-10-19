# Comparação isolada de uma posição de até 5 USDT

Execute `python small_cap_research.py`. Compara 5% por compra (até 1 USDT) com 25% (até 5 USDT), em carteira fictícia de 20 USDT, com custos normais e dobrados. O cenário de 25% altera somente esta pesquisa; não modifica configurações ou posições de outros processos.

Avalia 30 dias horários, após 60 horas de aquecimento. Uma posição por vez; entrada em recuo até 0,5% acima da média de 20 horas, com preço e média de 20 acima da média de 50 e retorno positivo em seis horas. Entre candidatos executáveis, prioriza maior retorno passado de seis horas. Nenhum sinal usa o fechamento da barra de execução. Vende por perda líquida de 2%, fechamento abaixo da média de 20 ou ganho líquido estimado de 1%. Executa na abertura seguinte com slippage adverso, portanto pode perder após sinal de lucro.

Taxa e slippage hipotéticos de 0,1% cada por lado no cenário 1x; 2x dobra ambos. Não são taxas consultadas da conta. Não há spread histórico observado, livro ou simulação de fila. Quantidade arredondada para baixo e conferida contra LOT_SIZE e notional atuais. Outros filtros não são reproduzidos. Com mínimo de 5 USDT, orçamento total de 5 USDT incluindo custos pode ser insuficiente; nunca aumenta automaticamente o orçamento.

Uma posição cujo valor caia abaixo do mínimo de venda, ou resíduos de lote, permanece na carteira e impede nova posição. O patrimônio final estima custos de saída mesmo que a liquidação não seja executável. Drawdown de 15% trava ordens, sem garantir venda; STOP é checado antes de cada ordem. Posições não são liquidadas obrigatoriamente no fim.

O universo usa liquidez e filtros atuais, não reconstruídos em cada data histórica: existe viés de seleção/sobrevivência. Ativos com histórico insuficiente são excluídos e identificados no relatório; a janela não é encurtada para incluí-los. Não serve como validação fora da amostra, comparação completa com mercado ou autorização de execução. Caixa parado tem resultado zero como referência da comparação. Resultados em `reports/local/small-cap-comparison.json`, exibidos separadamente no painel. Nenhum processo contínuo ou negociação real é iniciado.
