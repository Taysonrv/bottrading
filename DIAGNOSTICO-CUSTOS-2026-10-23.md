# Diagnóstico de custos — BTC/USDT 15m — 23/10/2026

**Sem aprovação.** A regra de cinco camadas apresenta três janelas positivas sem fricção; taxas isoladas, slippage isolado e os dois juntos tornam as quatro janelas negativas. A quarta janela já é negativa sem custos. Há sensibilidade relevante a custos, mas nenhuma vantagem líquida demonstrada.

| Cenário do candidato | Janela 1 | Janela 2 | Janela 3 | Janela 4 |
|---|---|---|---|---|
| Sem custos (irrealizável) | 4.93% | 4.87% | 1.00% | -1.97% |
| Somente taxa | -1.44% | -1.25% | -4.46% | -7.06% |
| Somente slippage | -2.51% | -1.39% | -4.26% | -7.30% |
| Taxa + slippage | -8.45% | -7.50% | -9.78% | -9.58% |

No cenário sem custos do candidato, 329 de 384 ciclos terminaram por sinal contrário (85.7%). Isso descreve o simulador e sugere investigar giro e duração, sem concluir que remover essas saídas melhorará o resultado.

## Escopo

Mesmos 70.176 candles e quatro janelas da comparação anterior; não há novo holdout. Cada janela reinicia 20 USDT fictícios. Não somar/compôr retornos. Duas regras fixas vezes quatro cenários = oito configurações neste diagnóstico, além das tentativas anteriores.

Sem custos é um contrafactual irrealizável. Taxa base: 0,1% por lado; slippage base: 0,1% por lado, como hipóteses. Não são tarifas individuais consultadas na conta.

Alterar custos muda stops, dimensionamento, saídas e momentos de acionamento das travas; a diferença entre retornos **não** é uma contribuição aditiva exata de taxa ou slippage. Os motivos e números de ciclos também podem mudar entre cenários.

Não foram reconstruídos spread, filtros históricos, fila LIMIT, liquidez ou ordens parciais. Não é teste da carteira de seis pares e não reproduz o executor ativo. O diagnóstico não muda a configuração nem cria ordens.

## Reprodução

```powershell
python -m spot_engine.cost_diagnostics --csv CAMINHO_DO_CSV_VALIDADO.csv --windows 4
python -m unittest tests.test_cost_diagnostics -v
```

O JSON em research_results/cost-diagnostics-20261023.json contém todas as linhas das duas regras, taxas, slippage, motivos de saída, PnL médio por ciclo, parâmetros e hashes. Os dados brutos permanecem locais.

## Próxima investigação

Auditar o giro, os motivos de saída e a hipótese econômica antes de introduzir outra variante. Não assumir que taxas zero, maker sem execução comprovada, stop removido ou menor slippage resolveriam o problema. Qualquer variante precisa de parâmetros fixados antes do teste, custos executáveis e dados fora da seleção já feita.

A estratégia ativa permanece em PAPER, sem vantagem aprovada. Este resultado não autoriza dinheiro real.

CSV SHA-256: `ac28586afb033cf4788fd73185eb6968287fa8227a5dbad1bb8993bbbca10b5b`
