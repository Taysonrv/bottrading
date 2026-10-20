# Coleta multipar por WebSocket, separada da execução

`node market_stream.js` requer Node 22+ com WebSocket global. Não precisa instalar pacotes. Consome apenas oito streams públicos: aggTrade e bookTicker para BTCUSDT, ETHUSDT, DOGEUSDT e PEPEUSDT, no domínio exclusivo de dados públicos Binance. Nenhum método de ordem, assinatura ou chave.

O processo dura até 24 horas e encerra ao encontrar STOP. Reconecta com espera progressiva de até 30 segundos; recomeça aquecimento após desconexão. Uma trava impede duas instâncias. Se houver interrupção abrupta, preserve/verifique o PID registrado antes de remover manualmente uma trava antiga. Não há reinício automático após reiniciar o computador.

A janela de até 60 segundos mostra volume em USDT (preço × quantidade), parcela de agressão compradora (m=false), spread do melhor bid/ask e variação entre primeiro e último negócio observado. Isso não é livro de profundidade, retorno de execução ou prova de absorção. Quantidades nominais de moedas diferentes não são comparadas diretamente.

Descarta IDs repetidos/fora de ordem e eventos de trades mais de 5 segundos atrasados ou 2 segundos à frente do relógio local. Lacunas de aggTrade reiniciam a janela do par. BookTicker tem idade de recebimento local, não latência exata da exchange, e aceita saltos no ID porque não é diff-depth. Sem livro ou negócio novo por 5 segundos não há gatilho. Sem mensagens válidas por 20 segundos força reconexão. Relógio incorreto pode bloquear eventos; não há medição confiável de latência fim a fim.

Observação experimental, fixa e não validada: janela aquecida por 60 segundos, ao menos 20 aggTrades, notional ≥10.000 USDT, participação de agressão compradora ≥65%, variação positiva e spread ≤0,1%. Exibe pressão compradora, nunca ordem. Limite de 10.000 negócios em memória por par reinicia aquecimento se excedido. Reconexão zera contagens da conexão; total de reconexões persiste apenas neste processo.

Grava relatório agregado local a cada 2 segundos em reports/local/market-stream.json. O painel relê a cada 10 segundos. Não guarda eventos brutos completos para replay, não simula IOC, não mede fills/slippage/latência de execução. Não substitui a estratégia nem a fonte de cotações da sessão contínua de 20 USDT.

Teste: `node test_market_stream.cjs`. Fontes oficiais:
- https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md
- https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams
