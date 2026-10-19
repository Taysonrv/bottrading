# Pesquisa de saídas do lote fictício inicial

```powershell
python exit_research.py
```

Usa a primeira compra registrada em `reports/local/live-paper-events.jsonl` e candles públicos de um minuto posteriores à entrada. Não altera `paper_lab.py`, carteira, estado de observação, validação ou ordens. Não é um comando para ativar take-profit.

Compara três hipóteses fixadas antes da execução:

1. Manter o lote inicial: referência sem vendas, não uma reprodução de decisões diárias futuras.
2. Take-profit: após fechamento de um minuto indicar ganho líquido estimado de 1%, solicitar vendas na abertura seguinte.
3. Proteção de lucro: após atingir 1% líquido nos fechamentos, solicitar saída depois de recuo de 0,5% do maior fechamento posterior à compra.

Uma vez disparada, a saída continua solicitando redução a cada minuto até zerar ou restar valor abaixo do mínimo, salvo STOP/drawdown. As vendas respeitam 5% do patrimônio por ordem. Não há reentrada ou aumento de posição. Quantidade restante continua marcada no patrimônio; não é descartada.

Custos de compra vêm das ordens fictícias iniciais. Venda usa abertura seguinte como referência, taxa de 0,1% e slippage de 0,1%; a abertura do candle não é o bid real e não reproduz spread, livro ou filtros atuais. Um gap pode produzir prejuízo mesmo após sinal de lucro. Máxima intraminuto sozinha não dispara saída: OHLC não revela toda a sequência de preços.

Ignora a vela que contém a compra para não usar preços anteriores à entrada. Exige candles contínuos e alinhados entre os ativos, período de 2 a 999 minutos e pelo menos dois candles fechados. Não pagina nesta etapa; falha se o histórico solicitado vier incompleto. Drawdown usa aproximação conservadora das mínimas simultâneas e mantém a política de bloquear ordens após o gatilho, sem garantir perda máxima.

Gera `reports/local/exit-comparison.json` e `.md`, ignorados pelo Git. O painel mostra a data do recorte e resultados separados do saldo ao vivo. Uma nova execução substitui esse relatório de pesquisa. Preservar amostras e registrar novas tentativas é necessário antes de qualquer seleção.

Amostra inicial curta: nenhuma das saídas disparou e os cenários tiveram o mesmo resultado. Não há evidência para adotar uma saída nesta etapa. As posições e a regra diária da sessão noturna permanecem inalteradas.
