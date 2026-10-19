# Cenário inicial: 20 USDT fictícios

Execute `python small_cap_scan.py` para atualizar uma fotografia de viabilidade. O painel mostra os resultados salvos, não realiza consultas contínuas nem executa ordens.

O universo são até 20 pares USDT em negociação Spot, dentro da lista explícita CRYPTO_BASES no código, ordenados por volume cotado das últimas 24 horas, com pelo menos 10 milhões de USDT negociados. Exclui moedas estáveis, moedas fiduciárias, ouro e sufixos de tokens alavancados. Não inclui ações tokenizadas ou ativos desconhecidos fora dessa lista. A lista não constitui recomendação.

O sinal experimental exige último fechamento horário acima da média de 20, média de 20 acima da de 50 e retorno positivo em seis horas. Spread máximo de 0,10%. São hipóteses ainda sem validação; não estimam lucro futuro.

Mantém 5% por ordem: com 20 USDT, até 1 USDT incluindo taxa/slippage hipotéticos de 0,1% cada na compra. Arredonda quantidade para baixo segundo LOT_SIZE e verifica mínimos e máximos de quantidade/notional atuais. Não reproduz todos os filtros Binance e não habilita execução, mesmo se encontrar candidato. Não aumenta orçamento para alcançar o mínimo.

Uma posição por vez é a regra prevista para eventual simulador multipar, ainda não ativado. Limites anteriores de exposição e drawdown continuam sem alterações. Este comando não toca configurações, sessões noturnas ou saldo real. Se todos os pares forem incompatíveis, o saldo fictício permanece integralmente em USDT e nenhuma ordem é criada.

Os filtros são consultados na API pública exchangeInfo. Fonte: https://developers.binance.com/en/docs/products/spot/filters

Saída local: `reports/local/small-cap-scan.json`, ignorada pelo Git. Repita o comando para atualizar. Erros em um par bloqueiam esse par; falha nas consultas globais não substitui o relatório anterior, cujo horário permanece visível.
