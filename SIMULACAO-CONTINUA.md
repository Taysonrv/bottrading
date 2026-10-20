# Simulação contínua de 20 USDT

`python live_small_paper.py --hours 24` inicia o experimento isolado de até 24 horas. Usa apenas GETs públicos Binance; não consulta conta ou envia ordens. Não interfere na carteira antiga, MetaMask ou pesquisa prospectiva. Requer computador acordado e internet. O painel sozinho não inicia este processo.

Saldo inicial fictício 20 USDT. Uma posição por vez; compra de até 5 USDT incluindo taxa e slippage hipotéticos de 0,1% cada. Limite de 25% exclusivo desta sessão, autorizado para simulação. Sinais de tendência/recuo em candles horários fechados, universo de criptomoedas com volume cotado atual. Entradas classificadas por momentum passado de seis horas; spread observado máximo 0,1%. Mínimos e LOT_SIZE observados, sem arredondar para cima. Não reproduz todos os filtros ou fila de ordens Binance.

Marca a carteira e avalia saídas a cada ciclo, aproximadamente 60 segundos. Vende por resultado líquido estimado de 1%, perda de 2% ou perda de tendência. Taxas e slippage podem causar perdas; proteção não garante preço de saída. Resíduos e quantidades abaixo do mínimo ficam expostos e impedem outra posição. No máximo uma entrada por candle horário.

STOP na pasta do projeto bloqueia cada ordem e encerra o processo; drawdown de 15% trava operações sem liquidação. O botão Desligar bot do painel cria esse STOP. O estado persiste, com trava de instância e hash do código. Não reinicia automaticamente saldo nem sessão expirada. Interrupções não têm preenchimento retroativo. Pode não haver nenhuma ordem quando sinais ou mínimos forem incompatíveis.

Arquivo local reports/local/live-small-paper.json guarda carteira, decisões, últimas 500 ordens e 1.500 medições. Gráfico não representa marcações ausentes; dados atrasados deixam de indicar atividade recente. O painel tem aba Simulação ao vivo com status, término, patrimônio líquido estimado, realizado, posição e ordens. Consultas de candles/filtros a cada nova hora; bid/ask a cada ciclo. Dados inválidos bloqueiam o ciclo. Resultados não aprovam a estratégia para execução real.
