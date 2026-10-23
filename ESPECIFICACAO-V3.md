# SpotLab v3.0 — especificação de pesquisa, não implantação

Data: 23/10/2026. Status: quatro hipóteses não validadas. O motor ativo, os pares atuais e sua carteira não são alterados por este documento ou pelo protótipo visual.

## 1. Correções do pedido

- As faixas de win rate, profit factor, beta e correlação fornecidas não têm evidência anexada. O padrão para todas é **desconhecido**. Não constam como resultados do produto.
- Binance Spot neste projeto é long/caixa; sem short, margem ou empréstimo. Funding é dado de derivativos, não custo cobrado no Spot.
- A nova lista BTC/ETH/SOL/BNB/LINK/AVAX é um universo candidato. Nenhum par recebe uma estratégia fixa por suposta personalidade. Todos passam pelas mesmas regras de regime. A migração de XRP/DOGE não está autorizada pelo resultado de pesquisa anterior.
- Com 20 USDT e exposição máxima de 40%, só 8 USDT poderiam estar investidos. Dividi-los em três saídas pode violar mínimos de ordem. Padrão: **não entrar** se qualquer parcela não passar nos filtros; sem arredondar para cima nem aumentar risco. A sessão atual continua com uma posição total, não seis.
- O protótipo `exports/spotlab-v3-demo.html` usa 10.000 USDT explicitamente fictícios para demonstrar densidade visual. Não se conecta à Binance, não tem chaves, não faz paper execution real e não muda os 20 USDT do bot.

## 2. Dados e indicadores exatos

Somente candles 15m fechados, UTC, ordenados e sem lacunas. Uma decisão no fechamento não permite preenchimento retrospectivo nesse fechamento: enviar após o candle e preencher em cotação posterior, incluindo atraso, spread e custos.

| Indicador | Definição padrão para pesquisa |
|---|---|
| EMA9/21/50, EMA200/4H, EMA50/diário | Alpha 2/(n+1), semente primeiro fechamento, adjust=False; aquecimento 3n |
| 4H e diário | Agregar 16/96 candles UTC completos; ignorar bucket inicial incompleto; liberar o candle superior somente após seu fechamento |
| RSI14 | Variações de fechamento; médias de ganhos/perdas iniciais por 14 períodos, depois Wilder; plano = 50 |
| MACD12/26/9 | EMA12−EMA26; sinal EMA9 do MACD; cruzamento só se condição anterior e atual forem observadas |
| ATR14 | True range máximo de H−L, abs(H−C anterior), abs(L−C anterior); Wilder14 |
| ADX14 | +DM/−DM de Wilder14, DI sobre ATR; DX suavizado14; sem divisão por zero |
| Bollinger20,2 | Média simples20 ± 2 desvios populacionais dos fechamentos |
| Volume relativo | Volume atual / média dos 20 candles anteriores, excluindo o atual; média zero = indisponível |
| OBV | Soma/subtração de volume pelo sinal da mudança de fechamento; crescente = OBV atual > OBV de 5 candles atrás |
| VWAP | Reset 00:00 UTC; soma de ((H+L+C)/3 × volume) / soma de volume, somente candles já fechados |
| Pivôs de divergência | Fundo com low menor que os 2 anteriores e os 2 seguintes; só confirmado após fechar o segundo candle à direita |

Sem todos os aquecimentos, inclusive 600 candles 4H e 150 diários, o regime é UNKNOWN e a decisão HOLD. Na série 15m isso exige pelo menos 150 dias completos para o filtro diário. Não usar candle 4H/diário ainda em formação.

## 3. Regime e quatro regras candidatas

Filtros comuns de long: fechamento 4H > EMA200/4H; fechamento diário > EMA50 diário; ATR/preço entre 0,5% e 2%, inclusive; corpo/range >= 0,40; volume relativo > 1,3; dados frescos; sem travas. Range zero reprova. RSI fora de 0–100 ou indicador ausente reprova.

Regime determinístico, nessa prioridade:

```text
if dados_incompletos: UNKNOWN
elif ATR/preco > .03: CRISIS
elif ADX14 > 25 and fechamento > maxima_dos_20_anteriores
     and volume_relativo > 1.3: BREAKOUT
elif ADX14 > 25 and EMA9 > EMA21 > EMA50: TREND
elif ADX14 < 20 and RSI14 < 45 and fechamento < VWAP: RANGE
else: TRANSITION
```

UNKNOWN, CRISIS e TRANSITION não abrem novas posições. Regime é classificação de regras, não inferência de vantagem. Nenhuma seleção automática é feita com base em PnL recente.

| Regra | Regime | Gatilho causal long |
|---|---|---|
| EMA Ribbon Trend | TREND | EMA9 cruza acima de EMA21; EMA9>21>50; MACD cruza acima do sinal; RSI45–65 |
| RSI Divergence | RANGE | Dois fundos confirmados separados por 5–32 candles; segundo preço menor e RSI pelo menos 5 pontos maior; RSI cruza acima de 35 após confirmação; fechamento recupera banda inferior |
| Breakout Volume | BREAKOUT | Fechamento > máxima dos 20 anteriores, excluindo atual; MACD>sinal; RSI45–65 |
| VWAP Reversion | RANGE | Candle anterior fecha abaixo da banda inferior; atual recupera banda; fechamento ainda abaixo do VWAP; RSI cruza acima de 35; distância até VWAP permite RR líquido mínimo |

As invalidações são, respectivamente: inversão EMA9<EMA21; perda do fundo confirmado; fechamento abaixo da antiga máxima rompida; afastamento além do stop estrutural/ATR. Nenhuma invalidação promete saída sem slippage.

O filtro de volume/OBV e filtros superiores também se aplicam às reversões; isso pode produzir pouquíssimos sinais. É uma hipótese pré-fixada a testar, não motivo para afrouxar depois de ver o histórico.

## 4. Score e seleção

Score é soma de cinco regras de 20 pontos: contexto superior e ribbon aplicável; momentum específico; gatilho específico+corpo; ATR+bandas aplicáveis; volume+OBV+VWAP alinhado à tese. Não é probabilidade calibrada.

```text
eligible = regime_compatível and gatilho and contexto_superior
           and dados_completos and score >= 70
```

Como incrementa de 20 em 20, score>=70 equivale a pelo menos 80. Empates entre pares: maior score, menor spread, nome do par em ordem alfabética. Uma posição por par e teto global proposto de duas posições, sem pirâmide. Com capital baixo, filtros podem permitir nenhuma.

## 5. Risco, tamanho e alvos

Padrões de pesquisa: risco 1% do patrimônio por operação; máximo 5% somado em stops, incluindo taxas/slippage estimados; exposição 40%; perda diária3% desde referência de abertura UTC; DD total10% travado; pausa após4 ciclos líquidos perdedores consecutivos até revisão manual. Vitórias zeram a sequência; zero não conta como vitória.

Não usar Kelly sem probabilidades e distribuição de retornos validadas. Score não aumenta risco acima de 1%. Tamanho base (unidades do ativo):

```text
stop_distance = 1.8 * ATR
risk_unit = entry*(1+fee) - max(0,entry-stop_distance)*(1-slip)*(1-fee)
score_factor = min(1, score/100)
qty = floor_to_step(min(equity*.01*score_factor/risk_unit,
                        free_cash/(entry*(1+fee)),
                        remaining_exposure/(entry*(1+fee))))
```

Validar tick/step, mínimo/máximo de quantidade, notional e saldo antes de cada parcela. Não assumir que uma ordem pequena passa por ter sinal forte.
SL inicial entry−1,8ATR. TP1=entry+2ATR com40%, TP2=entry+3,5ATR com35%, TP3=entry+5ATR com25%. Alocar as duas primeiras quantidades arredondando para baixo; a terceira recebe o restante. **Cada** parcela deve passar nos filtros. Não elevar capital ou quantidade para fazer a regra passar.

O TP1 sozinho tem RR bruto 2/1,8=1,11. O conjunto ponderado tem RR bruto (0,4×2+0,35×3,5+0,25×5)/1,8≈1,82. O requisito1,5 será aplicado ao plano ponderado **líquido**: custo total de entrada versus receita líquida ponderada / perda líquida no stop. Se RR líquido<1,5, HOLD. Não apresentar TP1 como1,5R.

Breakeven após movimento favorável0,8R usa preço que cobre compra, venda e slippage previsto, não apenas o preço de entrada. Nunca afrouxar stop. Trailing após1,5R: máximo(stop anterior, máxima observada após entrada−1,8ATR); atualizado só com dado já conhecido. Saída parcial não deixa restos inexequíveis.

## 6. Prioridades e bloqueios

Controle de risco não fica atrás do alvo. Antes de **cada** ordem: autenticação, modo, kill switch, integridade, relógio, dados, limites e filtros. Não permitir que um TP contorne STOP ou falha de API.

Padrão proposto para um executor futuro: pausa de entradas e pedido de redução de risco são controles distintos; emergência tenta cancelar entradas e reduzir posições apenas se existir executor saudável e permissões válidas. Nunca promete “fecha tudo instantaneamente”. O STOP do motor atual continua bloqueando compras e vendas e não liquida nada.

Prioridade econômica dentro de uma posição, depois das permissões operacionais: stop/gap; redução por limite de risco ou flash crash; alvos; sinal contrário; inversão EMA9/21; time stop32 candles15m (8h). Em candle ambíguo de backtest, stop primeiro. Uma saída precisa de cotação posterior e pode falhar por liquidez/filtros.

Filtros pré-fixados: bloquear entradas05:00≤UTC<09:00; calendário macro±30min; funding positivo>0,15% (0,0015, taxa crua, sem anualizar) como contexto opcional de derivativos; flash crash BTC: queda de3% em5min, consultada em dados de1min, suspende entradas por30min e exige revisão se houver posição. Sem fonte fresca de calendário/funding/BTC1m quando o filtro estiver habilitado, não operar. Esses dados não estão conectados no protótipo.

Não declarar BNB pouco correlacionado, LINK com beta2,2 ou padrões confiáveis de AVAX sem medições fora da amostra. Essa preferência por par é retirada da especificação operacional.

## 7. Validação e promoção

Quatro estratégias + regime + parâmetros + custos multiplicam tentativas. Registrar todas, incluindo resultados negativos e sem trades. Não selecionar vencedores no histórico já utilizado pelo projeto.

1. Testes causais, indicadores e agregação superior; confirmação atrasada de pivôs, sem leakage.
2. Pelo menos2 anos por par, com aquecimento superior fora da janela avaliada e filtros históricos quando disponíveis.
3. Simulação única da carteira e conflitos entre sinais, não seis caixas independentes. Taxas, spread, slippage, atraso, filas, parciais e mínimos precisam ser representados.
4. Walk-forward com treino/validação/holdout temporal; parâmetros congelados antes do holdout. Comparar com caixa e buy&hold usando a mesma exposição/capital; registrar viés de seleção.
5. Resultados líquidos por janela/regra/par, incerteza por bootstrap em blocos, degradação em custos2×. Nenhuma meta de win rate aprova isoladamente.
6. Se aprovada na pesquisa, nova sessão paper separada; Testnet2–4 semanas como teste operacional. Live continua bloqueado até avaliação própria e autorização concreta. O protótipo não implementa essa promoção.

O candidato anterior já teve perdas com custos em BTC15m. Este documento não apaga esse resultado nem fornece evidência de que quatro regras resolveriam o problema.

## 8. Pré-operação, incidentes e diário

Pré-operação: confirmar modo; versão/hashes; prazo; uma carteira reconciliada; ausência de processo duplicado; STOP; fontes UTC recentes; aquecimentos; saldo livre; filtros e parcelas; limites diários/DD; fila de alertas. Bloquear diante de falha, sem remover travas automaticamente.

Encerramento: reconciliar fills/cancelamentos/taxas; verificar exposição residual e ordens pendentes; comparar saldo com ledger; preservar logs e dados; registrar lacunas; nunca marcar posição aberta como lucro realizado.

| Incidente | Ação |
|---|---|
| Rede/API fora | Pausar entradas, registrar, conservar estado; não preencher em preço velho |
| Ordem com resposta desconhecida | Consultar estado pelo ID idempotente antes de tentar novamente; nunca duplicar |
| Parcial/resto abaixo do mínimo | Reconciliar quantidade real; sem fingir liquidação; intervenção documentada |
| Ledger/identidade inválidos | Bloquear execução e preservar arquivo; não reiniciar saldo |
| Dados superiores ou calendário faltando | HOLD com motivo; não usar filtro aprovado artificialmente |
| Kill switch | Mostrar sua semântica exata; confirmar exposição restante; sem promessa de fechamento |
| PC suspenso/processo morto | Registrar intervalo desconhecido ao retomar; supervisão do SO é necessária para disponibilidade contínua |

Diário: UTC; versão; par/regra/regime; candle15m/4H/diário de referência; indicador/score e motivo de cada bloqueio; qty/preço solicitado/preenchido; slippage observado; taxas; stop/alvos; sequência de perdas; exposição; risco; cancelamentos; atraso e falhas. Nunca registrar chaves ou secrets.

## 9. Entrega visual

O HTML único demonstra12 módulos, com dados MOCK e atualização local por timer. Todos os controles mudam **apenas o cenário fictício**. Não usa fetch, WebSocket, SDK de exchange ou carteira. A evolução visual não é evidência de resultado ou de integração operacional.
O painel real existente permanece separado. Os pontos [CONECTAR: ...] no protótipo exigem APIs autenticadas, autorização, reconciliação, testes e validação antes de receber dados reais ou controlar ordens.

Fontes técnicas consultadas23/10/2026:
- https://developers.binance.com/en/docs/products/spot/filters
- https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data

As fontes descrevem filtros e dados; não comprovam nenhuma das faixas de desempenho citadas no prompt.
