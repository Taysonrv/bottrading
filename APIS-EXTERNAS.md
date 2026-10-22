# APIs externas gratuitas — contexto, sem ordens

Integrações pessoais, sem chave e sem conexão à carteira real:

| Fonte | Conteúdo | Cadência |
| --- | --- | --- |
| Alternative.me | Índice diário de sentimento do Bitcoin | Consulta a cada 6h; data original preservada |
| CoinPaprika | Preços agregados USD de BTC, ETH, SOL, BNB, XRP, DOGE | 6 chamadas a cada 15min, aproximadamente 17.856/mês de 31 dias |
| GeckoTerminal | Amostra de até 3 pools da primeira página por rede BNB Chain, Polygon e Solana | Até 3 chamadas a cada 15min |

Não são fontes de preço para a execução Binance/USDT. Não confirmam cruzamentos, não geram ordens e não mudam limites de risco. A diferença USD/USDT e o horário de atualização tornam incorreto tratar esses preços como arbitragem executável.

O iniciador operar.py atualizado tenta ativar um coletor independente em segundo plano. Falhas no coletor não encerram trading. Caso ele já esteja ativo, a trava evita outro coletor. Para executar isoladamente sem reiniciar o motor:

```powershell
.\.venv-spot\Scripts\python.exe external_context.py --watch
```

Sem --watch faz uma rodada, respeitando o cache existente. Com --data-dir pode apontar à pasta de dados usada pelo painel. O arquivo reports/local/external-context.json guarda somente dados públicos, horários e falhas genéricas. Nenhum saldo, endereço de carteira ou chave é enviado.

Falhas mantêm o último dado salvo explicitamente desatualizado. HTTP429 aplica espera de pelo menos 1h. GeckoTerminal mantém sucessos por rede quando outra rede falha, e deixa de consultar redes restantes ao receber 429. Não há desvio de bloqueio, chave paga ou renovação de cota automática.

O plano gratuito CoinPaprika é pessoal, não comercial, com limite compartilhado por IP; outras aplicações no mesmo IP também consomem cota. Atribuições ficam junto aos dados no painel. Dados de pools são amostra pública, não uma avaliação dos ativos MetaMask ou garantia de liquidez de saída.

Fontes oficiais consultadas: https://alternative.me/crypto/fear-and-greed-index/ ; https://coinpaprika.com/api ; https://apiguide.geckoterminal.com/getting-started ; https://support.coingecko.com/hc/en-us/articles/22612838274841-Does-GeckoTerminal-have-an-API

Os limites e termos podem mudar. Um dado ausente não é zero. Falha ou dado vencido não autoriza substituição automática na estratégia. Não usar histórico do índice como se ele estivesse disponível antes de sua publicação.
