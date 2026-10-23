# V3 — indicadores e quatro regras offline — 23/10/2026

Implementado em spot_engine/v3_research.py, separado do motor ativo. Calcula EMA9/21/50, MACD12/26/9, RSI14, ATR14, ADX14, Bollinger20,2, OBV, volume relativo20 e VWAP com reset UTC. Agrega candles completos4H e diários para EMA200 e EMA50. A confirmação de pivô exige dois candles à direita; não é retroativa.

Regras: EMA Ribbon, RSI Divergence, Breakout Volume e VWAP Reversion. Há classificação de regime, pontuação e filtros de contexto, corpo, ATR, volume e horário05–09UTC. A classe só produz candidaturas de pesquisa: action permanece HOLD e execution_authorized permanece false. Não contém dimensionamento, SL/TP, trailing, parciais, filtros externos, acesso à carteira ou envio de ordens.

## Inspeção em dados reais

- Universo examinado aqui: **somente BTC/USDT**, não os seis pares.
- Candles15m: 70,176; após aquecimento superior: 55,694.
- Candidaturas: EMA Ribbon0, RSI Divergence0, Breakout Volume0, VWAP Reversion0.
- ATR fora de0,5%–2%: 51,554 de 55,694 avaliações após aquecimento (92.57%).
- Último regime: TRANSITION.

Contagens de falhas de camadas se sobrepõem; não somar como motivos exclusivos. A camada de tendência também inclui compatibilidade de regime. Falhar em ATR não prova que ele seja a única causa de ausência de sinais.

**Sem backtest, sem retorno estimado e sem aprovação.** Candidaturas não são ordens ou fills. O resultado zero permanece publicado; não foram reduzidos limites para gerar operações.

## Inconsistência de score exposta

As cinco confirmações foram especificadas como obrigatórias. Cada uma vale20 pontos. Portanto uma candidatura que passa em todas já soma100; score>=70 é redundante. Não transformar uma regra obrigatória em opcional depois de olhar este resultado. Uma definição alternativa de score constitui outra hipótese e precisa ser registrada antes de teste independente.

## Uso

```powershell
python -m spot_engine.v3_research --csv CAMINHO_DO_CSV_VALIDADO.csv
python -m unittest tests.test_v3_research -v
```

O CSV e seu manifesto vêm do coletor. A inspeção é incremental e não guarda todos os snapshots na memória ao executar a CLI. O relatório integral, com indicadores finais, contagens e hashes, está em research_results/v3-inspection-20261023.json.

## Limitações e próximos requisitos

São regras novas não validadas. Não são usadas pela sessão ativa. Funding, calendário macro e flash crash BTC não estão conectados; os dados de contexto ausentes nunca autorizam trading neste módulo. Não há implementação de carteira multipar v3, sizing, risco ou saídas propostos na especificação. O cálculo usa floats de pesquisa, não o ledger decimal.

Limite numérico de entrada: preços OHLC entre1e-12 e1e15 e volume até1e15 por campo para proteger a aritmética. Candles incompletos, duplicados, desalinhados, lacunas e relógio de decisão regressivo são rejeitados antes de atualizar o estado. Buckets superiores iniciais incompletos não são usados. VWAP sem volume e indicadores sem aquecimento ficam indisponíveis.

Antes de qualquer promoção: testes adicionais de indicadores com fixtures independentes, inspeção dos outros pares, backtest com execução/custos realistas, validação temporal independente e nova sessão paper separada. Não atribuir as faixas de acerto/PF fornecidas no prompt a este código.
