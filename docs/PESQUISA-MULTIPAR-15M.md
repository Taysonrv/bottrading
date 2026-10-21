# Pesquisa multipar em 15 minutos

O módulo `spot_engine.universe_research` coleta dois anos de candles públicos
para BTC, ETH, SOL, BNB, XRP e DOGE contra USDT. A janela final é fixada antes
da primeira coleta e compartilhada pelos seis pares.

Cada par é avaliado separadamente com capital fictício de 20 USDT, teto de
6 USDT por entrada e os mesmos parâmetros EMA/ATR. São quatro períodos
cronológicos, cada um precedido de 600 candles de aquecimento. Os períodos
reiniciam capital e controles de risco: seus retornos não devem ser compostos
como uma única carteira. Há dois cenários de custos, totalizando 12 variantes
de par/custo e 48 avaliações de período.

Execução manual a partir da pasta do projeto:

```powershell
.\.venv-spot\Scripts\python.exe -m spot_engine.universe_research
```

O comando cria uma pasta única em `reports/local/spot-universe`, com índice,
CSVs, manifestos de integridade e relatórios. Nunca substitui a carteira em
andamento. Não necessita de chave Binance. O painel Estratégias lê os relatórios
concluídos sem iniciar pesquisas automaticamente.

Os resultados são exploratórios. Não há otimização, treinamento de modelo ou
aprovação automática. Não reproduzem filtros históricos de lote/mínimo, fila,
spread, latência ou preenchimentos parciais. O simulador usa frações que podem
ser inviáveis com 20 USDT. A hipótese de stop intrabar não limita perdas reais.
Não são um backtest da carteira multipar com seleção e saldo compartilhado.
Comparar muitos pares/cenários aumenta a chance de achar um período positivo
por acaso. Uma nova hipótese precisa de protocolo fixado antes de examinar
novos dados e posterior teste prospectivo.

Testes:

```powershell
.\.venv-spot\Scripts\python.exe -m unittest tests.test_spot_universe_research tests.test_spot_temporal_validation tests.test_spot_research_view -v
```
