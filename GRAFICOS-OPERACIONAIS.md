# Gráficos operacionais e mapa 3D

Bot ao vivo agora inclui seletor BTC/ETH/SOL/BNB/XRP/DOGE, com candles Binance de 15m. A interface consulta a rota autenticada /api/live-market a cada 30 segundos, somente enquanto o Terminal está visível. Não é feed tick a tick ou WebSocket. Cache do servidor também é de 30 segundos.

O último candle pode estar em formação; a estratégia continua usando candles fechados. Falhas mantêm o último gráfico com data e aviso, sem inventar preço. Stop e alvo aparecem apenas se a posição registrada corresponde ao par selecionado; são proteção sintética da simulação, não ordens na exchange.

O mapa 3D usa seis pontos no máximo, exclusivamente de linhas válidas do radar. X é EMA20/EMA50 menos um; Y é preço/EMA200 menos um; Z é ATR/preço. Cada eixo é normalizado pelo maior módulo da amostra atual. Não é correlação, aprendizado de máquina ou previsão. Linhas ligam pontos à origem para orientação geométrica; não significam relacionamento econômico.

Arrastar gira a projeção; botões permitem rotação e restauração sem arrastar. Pontos vencidos ficam atenuados e o horário da coleta é exibido. Não há animação automática ou posição aleatória. Sem dados, não são criados pontos fictícios. Renderização Canvas2D com projeção espacial, sem biblioteca externa, GPU/WebGL ou serviço pago.

Essa interface não altera carteira, estratégia, riscos ou ordens. Para tick a tick, seria necessário um feed WebSocket com reconexão e validação próprios; não confundir as duas velocidades.
