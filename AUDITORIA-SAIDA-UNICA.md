# Auditoria da hipótese de saída única

O replay reproduziu exatamente o experimento salvo de BTC/USDT 1h, com capital fictício de 20 USDT. Nenhum parâmetro foi ajustado e nenhuma estratégia foi aprovada.

| Saída | Ciclos | Resultado líquido USDT |
|---|---:|---:|
| Stop | 25 | -3,252260 |
| Alvo | 4 | +1,058550 |
| Tempo (48h) | 26 | +0,314125 |
| Total | 55 | -1,879584 |

Nas mesmas quantidades e referências de entrada/saída, a variação dos preços contribuiu **-0,636694 USDT**, slippage e arredondamento contribuíram **-0,621458**, e taxas **-0,621431**. Isso reconcilia o líquido. Não é um backtest sem custos: removê-los mudaria preços, tamanhos, filtros e trajetória. Os custos agravam um resultado de referência já negativo.

A taxa de acerto foi 18/55 (32,73%). Apenas quatro ciclos atingiram o alvo; os 25 stops dominaram as perdas. Essas são descrições da amostra já inspecionada, não evidência para escolher novos parâmetros. O cenário de custos dobrados tem 41 ciclos e trajetória diferente; não se deve atribuir sua diferença de retorno somente às taxas.

## Reprodução

```powershell
python -m unittest tests.test_single_exit_audit tests.test_single_exit_research -v
python -m single_exit_audit --csv CAMINHO_DO_CSV_ORIGINAL --baseline research_results/single-exit-20261025.json
```

O CSV precisa ter o hash do experimento original. O comando não acessa rede nem carteira. Grava relatório JSON e dois diários CSV em `reports/local/single-exit-audit/`, preservando relatórios anteriores. A tela V3 lê `latest.json` nessa pasta. Use `--data-dir` quando o painel utilizar outra pasta de dados.

O diário registra cada ciclo, motivo, taxas, execução, duração e limites de excursão por candle. MAE/MFE usam extremos do candle completo, que podem acontecer após uma saída intrabar; não representam extremos executáveis. Filtros atuais projetados no passado e ausência de fila/latência observada continuam limitações.

Próxima decisão: formular uma hipótese nova com justificativa econômica e protocolo congelado antes de testá-la. O histórico já visto não pode ser apresentado como amostra independente. A auditoria não reinicia sessões, não altera saldo e não habilita ordens.
