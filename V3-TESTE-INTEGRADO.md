# V3: sinal, orçamento e execução são etapas diferentes

24/10/2026. Continuação do roteiro de dez blocos. Este diagnóstico não modifica
spot_engine/, ai_shadow/, v3_engine/ ou a identidade das sessões em andamento.
Os módulos novos ficam na raiz para não invalidar o observador de 48h.

## Auditoria dos mínimos reais atuais

`v3_feasibility.py` consulta somente exchangeInfo, bookTicker e horário da
Binance pública. Reutiliza ATR/score do observador recente; não lê contas ou
chaves e não envia ordens. Consulta pontual não é feed de execução.

Na consulta dos quatro pares BTC/ETH/SOL/BNB USDT, o mínimo normalizado foi
**5 USDT por ordem**. O plano V3 atual exige três parcelas, todas válidas
inclusive na proteção de stop. Portanto, só o notional agregado mínimo dessas
três parcelas já é **15 USDT**. Isso é uma condição necessária, não um plano
viável nem sugestão de capital: custos, quantidades, pesos 40/35/25 e preço de
stop podem exigir mais. Um teto total de entrada de 5 USDT é incompatível.

A auditoria mantém dois diagnósticos separados:

- Plano com o score real do observador: os quatro pares reprovaram por score
  baixo na consulta inicial.
- Teste explicitamente hipotético com score100, sem alterar ATR/preço:
  os quatro reprovaram ATR_RANGE. Isso não é sinal de compra nem razão para
  reduzir o filtro de volatilidade depois de observar os resultados.

O bloqueio matemático do teto e os bloqueios de sinal/ATR podem coexistir.
Não confundir o primeiro motivo retornado pelo planejador com a única condição
que impede a entrada. O painel mostra ambos e o instante da consulta salva.

## Teste integrado das classes V3

`v3_backtest.py` conecta as classes reais do pacote: contexto incremental,
regime, score, plan_entry, risco, posição ATR, três saídas e trailing/time stop.
Entrada usa somente o sinal anterior fechado, no próximo open com slippage;
ATR também vem do candle anterior. Caixa inclui taxas nas compras e vendas;
PnL de parcelas é reconhecido proporcionalmente. O final liquida inventário
hipoteticamente, sem inventar um candle futuro. Caixa final reconcilia com a
soma dos ciclos líquidos. Sem aquecimento superior, o teste recusa o histórico
em vez de apresentar zero retorno como resultado válido.

No CSV BTC 15m previamente estudado, com 70.176 candles e capital fictício 20 USDT:

| Métrica | Resultado |
|---|---|
| Candidatos das regras V3 | 2 |
| Rejeições | 2 por PARTIAL_EXIT_FILTER |
| Ciclos executados no modelo | 0 |
| Retorno líquido hipotético | 0% |
| Acerto / profit factor / Sharpe | Indisponíveis, não zero |
| Veredito | NO_TRADES_NOT_VALIDATED |

Este é o teste das classes V3, distinto das17 janelas negativas da EMA antiga.
**Não houve lucro demonstrado nem aprovação de estratégia.**

## Limitações que impedem promoção

Os filtros atuais são projetados como constantes no passado, explicitamente
contrafactuais. Não afirmamos que estavam disponíveis nesses candles. Não há
reconstrução de spread, book, fila, latência, liquidez nem todos os filtros da
exchange. Stops são sintéticos; em ambiguidade intrabar, o stop vem primeiro.
Novos stops de trailing/breakeven só valem no próximo candle. Saídas a mercado
hipotéticas podem ser inexequíveis pelos filtros futuros/condições do livro.
Daily/DD são avaliados nas aberturas/fechamentos, não em equity intrabar contínuo.
Uma amostra já inspecionada de um único par não é holdout independente ou teste
da carteira multipar. Os demais pares ainda não têm esse histórico integrado
avaliado. Nenhuma ausência de fill comprova vantagem ou segurança.

## Comandos

```powershell
git pull
python -m unittest tests.test_v3_backtest -v
python -m v3_feasibility --data-dir .
python -m v3_backtest --csv CAMINHO-CSV --filter-snapshot reports/local/v3-feasibility/latest.json --data-dir .
```

O CSV exige o manifesto original ao lado. O relatório completo usa um UUID;
`reports/local/v3-backtest/latest.json` contém apenas resumo para a viewV3.
O painel não mistura o resultado com o saldo da carteira ativa. A viabilidade
fica em `reports/local/v3-feasibility/latest.json`; é uma consulta pontual e
nunca é apresentada como cotação atual no gráfico.

## Próxima hipótese a estudar

Para capital pequeno, a política de três parcelas sob esse teto é inexequível.
Uma saída única é uma hipótese separada a comparar, com risco e custos iguais,
sem aumentar capital, teto ou frequência para forçar trades. TP 2 ATR com
SL 1,8 ATR oferece somente 1,11R bruto e já falha no requisito 1,5R líquido.
Não migraremos o motor ativo com base nessa combinação. A observação de 48h e
a revisão humana continuam obrigatórias e não são preenchidas pelo replay.

## Evidência publicada

- `research_results/v3-feasibility-20261024.json`: consulta pública pontual.
- `research_results/v3-integrated-backtest-20261024.json`: resumo integrado V3.
- `research_results/v3-backtest-filter-assumption-20261024.json`: cópia exata do
  snapshot usado, cujo SHA256 confere com o relatório. Contém dados públicos,
  sem credenciais, contas ou carteira. Preservado mesmo após nova consulta.
