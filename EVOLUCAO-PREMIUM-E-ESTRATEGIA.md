# Interface e candidato de pesquisa — 23/10/2026

Os dois textos de referência são propostas de produto. Não são evidência de vantagem estatística, autorização para ordens reais ou justificativa para trocar o motor de uma sessão em andamento.

## Entregue neste pacote

| Proposta | Implementação / limite |
|---|---|
| Workspaces | Visão geral, gestão de risco, análise de pares e acesso ao Diagnóstico; preferência local no navegador |
| Tema | Escuro, claro e terminal verde; não altera configuração financeira |
| Foco | Painéis principais abrem em diálogo ampliado; Escape/Voltar devolve o painel à posição original |
| Relógio | Brasília e UTC simultâneos |
| Histórico | Busca por par, lado, motivo e estado; CSV do recorte recebido, com proteção contra fórmulas em células |
| Performance | Médias líquidas de ganhos/perdas, sequências máximas e ciclos por par, além de acerto e profit factor existentes; somente histórico completo |
| Estratégia em camadas | Módulo offline `spot_engine/layered_research.py`, sem acesso à carteira ou executor |
| Execução atual | Preservada: uma posição **no total**, não uma por par, saldo compartilhado de 20 USDT fictícios |

Continuam existentes: gráfico público 15m, referências sintéticas de stop/alvo, radar dos seis pares, mapa de indicadores, fila de alertas, contexto de mercado e monitor amostral de disponibilidade. Seus dados não são substituídos por variação aleatória.

## O que não está implementado ou não deve ser apresentado como pronto

Não há painéis arrastáveis/redimensionáveis, VaR, matriz de correlação, telemetria CPU/RAM, distribuição p50/p95/p99 de latência da exchange, série diária de patrimônio reconciliada, metas diárias, calendário macro automático, rotação de ativos ou indicador calibrado de confiança.
O monitor de disponibilidade mede intervalos amostrados; não é uptime comprovado do processo. O horário de atualização não mede latência da exchange.
Pausar entradas, fechar tudo, editar stops e mudar risco durante a sessão não têm API operacional. Os controles correspondentes permanecem desabilitados. STOP impede ordens e não promete liquidação.
Não há short, futuros ou alavancagem. Funding e open interest seriam contexto adicional de derivativos, não condição já implementada para Spot.

## Hipótese de estratégia

Estilo: seguimento de tendência com cruzamento EMA20/50, contexto EMA200, ATR e confirmações de momentum/volume. Hipótese a testar: cruzamentos alinhados à tendência com participação de volume podem ter melhor continuidade líquida que cruzamentos sem filtros. Não há resultado que confirme essa hipótese.
15m é mantido para comparação com a experiência atual. A mudança para 5m, 1h ou 4h seria uma variante adicional a registrar, não um ganho presumido. Frequência, acerto e drawdown esperado são desconhecidos.

O candidato offline calcula:

| Camada | Regra candidata |
|---|---|
| Tendência | Fechamento > EMA200 e EMA20 > EMA50 |
| Momentum | RSI14 de Wilder entre 50 e 70, inclusive, e MACD12/26 > sinal EMA9 |
| Timing | Intenção ENTER_LONG da estratégia EMA/ATR existente no candle fechado |
| Volatilidade | ATR14/preço entre 0,1% e 5%, conforme configuração conservadora existente |
| Volume | Volume atual >= 1,2 × média dos **20 candles anteriores**, excluindo o atual |

Cada regra soma 20 pontos. Um candidato exige pelo menos 80, com tendência, timing e volatilidade obrigatórios. Falta de volume não aprova a camada. RSI fica indisponível antes de 14 variações; preço plano tem RSI50. Não existe probabilidade de lucro derivada dessa contagem.
Os parâmetros são hipóteses iniciais fixadas para teste, não valores ótimos. RSI14 permite uma confirmação de momentum com suavização conhecida, mas pode descartar tendências fortes acima de 70. MACD e médias são parcialmente redundantes; volume pode ser instável por regime. O filtro adicional pode piorar o resultado e reduzir demais a amostra.
Há aquecimento mínimo de 600 candles; timestamps futuros, duplicados e lacunas são rejeitados. Um resultado offline não equivale a backtest ou autorização de compra.

Uso com CSV e manifesto produzidos pelo coletor existente:

```powershell
python -m spot_engine.layered_research --csv CAMINHO_DO_HISTORICO.csv
python -m unittest tests.test_layered_research -v
```

O comando apenas lê histórico validado e imprime uma inspeção do último candle. Não baixa dados, não simula PnL e não altera a sessão ativa.

## Capital, saídas e restrições preservadas

O motor compartilhado mantém teto de 6 USDT por entrada, uma posição total, stop sintético de 2%, alvo de 4%, risco previsto de até 1% do capital, limite diário de 3% e drawdown de 10%. O dimensionamento e os filtros devem continuar no código determinístico. O novo score não muda tamanho de posição.
O motor considera cotação posterior, slippage e taxas estimados; não garante executar no nível do stop. As taxas usadas na simulação são hipótese de custo, não tarifa individual consultada na conta.
Não foram adicionadas saídas parciais, pirâmides, Kelly, breakeven, trailing ou time stop. Com 20 USDT, repartir ordens pode esbarrar em mínimos e precisão. Reduzir valores para contornar filtros é inválido.
A saída existente prioriza o sinal contrário no motivo registrado quando coincide com outras condições; não foi reordenada silenciosamente para corresponder ao pseudocódigo do documento. Risco e STOP têm semânticas diferentes: STOP manual bloqueia venda também, preservando exposição.

## Seleção e risco de mercado

BTC, ETH, SOL, BNB, XRP e DOGE permanecem como universo fixo de comparação. Não se afirma que sejam a seleção ótima hoje. A escolha de uma única posição elimina múltiplas exposições simultâneas dentro deste motor, mas não elimina risco direcional ou correlação em testes futuros.
Spread e filtros são reavaliados pelo motor existente; a inspeção offline não sabe spread, liquidez, saldo ou book disponíveis no momento de execução. Ela não pode autorizar entrada.
Não há janela horária, filtro diário, calendário macro ou bloqueio por flash crash adicionados. Devem ser variantes pré-definidas, testadas sem escolher retrospectivamente os melhores horários.

## Validação antes de promover o candidato

1. Fixar versão, parâmetros e todas as variantes tentadas. Usar pelo menos dois anos de candles contínuos por par e documentar lacunas e limites dos dados.
2. Separar treino, validação e holdout por tempo. Fazer walk-forward; o holdout final só é consultado após fixar a escolha. Tentar variantes aumenta o risco de seleção por acaso.
3. Reproduzir a carteira compartilhada e escolha de um único sinal, mínimos, precisão, taxas, spread, slippage, atraso e cancelamentos. Um teste independente por par com 20 USDT cada não representa esta carteira.
4. Comparar com caixa e comprar/manter, usando a mesma janela e capital. Reportar retorno líquido, drawdown, Sharpe com convenção explícita, ciclos, acerto, profit factor e exposição.
5. Examinar sensibilidade a custos maiores, estabilidade entre janelas e bootstrap em blocos. Não fazer Monte Carlo de retornos independentes como se a dependência temporal desaparecesse.
6. Não usar acerto mínimo isolado como aprovação. Poucas perdas grandes podem anular muitos ganhos. Sem amostra suficiente, intervalos de incerteza e resultado consistente fora da amostra, o veredito deve ser inconclusivo.
7. Só depois executar nova sessão paper separada e Testnet por 2–4 semanas, distinguindo comportamento operacional de evidência de rentabilidade. Live permanece indisponível neste pacote.

## Operação e incidentes

Antes de iniciar: confirmar PAPER, prazo, trava STOP, integridade/identidade da carteira, saldo compartilhado, apenas um supervisor, dados recentes, filtros disponíveis e ausência de credenciais de saque. Não remover STOP apenas para fazer a pré-verificação passar.
Ao encerrar: revisar ordens canceladas, preenchimentos, custos, exposição ainda aberta, lacunas de coleta e limites acionados; preservar o ledger. Caixa não significa erro e um sinal não significa preenchimento.
Exchange indisponível: não usar cotação velha como execução; conferir os códigos e logs, preservar a posição e revisar antes de retomar. Supervisor encerrado: investigar diário e lacuna; o monitor não recupera energia ou internet.
Posição presa por liquidez/mínimos: registrar a causa, não inventar preenchimento e não prometer liquidação instantânea. Operação real eventual exigiria um plano próprio de intervenção humana.
Diário sugerido: versão/configuração, início/fim, tempo desconhecido, candidatos, reservas, cancelamentos, fills, taxas, resultado realizado, exposição e motivo de cada trava. Não reotimizar automaticamente durante a noite; alterações exigem novo ciclo de validação.

## Fontes técnicas verificadas em 23/10/2026

- Filtros de preço, quantidade e notional: https://developers.binance.com/en/docs/products/spot/filters
- Dados públicos de mercado e candles: https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market

As fontes documentam a API, não comprovam o edge do candidato. O risco principal continua sendo uma regra que parece plausível, mas perde depois dos custos e da seleção de parâmetros.
