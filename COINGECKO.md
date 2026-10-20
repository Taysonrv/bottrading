# Contexto CoinGecko

Camada opcional e independente da simulação: BTC, ETH, SOL e DOGE. Usa GET /coins/markets, ids explícitos e moeda USD; não usa cotação agregada para executar, selecionar sinais ou marcar posições Binance em USDT. Não inclui pools onchain nesta versão.

Crie sua chave Demo diretamente em https://www.coingecko.com/en/api e configure no terminal local:

```powershell
.\configurar-coingecko.ps1
python iniciar.py
```

Não envie a chave no chat. Ela fica somente na variável COINGECKO_DEMO_API_KEY deste terminal e é enviada no cabeçalho x-cg-demo-api-key ao host oficial. Não é gravada no relatório ou exposta ao navegador. Sem a chave, a fonte fica desativada.

Uma requisição conjunta a cada 900 segundos enquanto o iniciador estiver ativo (aproximadamente 2.880 chamadas em 30 dias contínuos; outros usos da conta também consomem cota). Tentativas são persistidas para limitar consultas após reinício. Falhas preservam os últimos dados e aguardam o intervalo. Os limites e a disponibilidade dependem do seu plano. Cache local em reports/local/coingecko-context.json, ignorado pelo Git. Consulta manual: python coingecko_feed.py (também respeita o intervalo).

A tela distingue horário da consulta e horário da fonte; dados com mais de 30 minutos são sinalizados como antigos. Não inclui WebSocket nem troca automática da fonte Binance. Fontes: https://docs.coingecko.com/demo/reference/coins-markets e https://docs.coingecko.com/demo/reference/authentication.

## Validação e diagnóstico

O configurador agora valida uma chamada autenticada imediatamente e só confirma sucesso após receber dados válidos. Aceita a chave Demo com espaços/aspas externos ou uma URL HTTPS oficial com x_cg_demo_api_key; extrai a chave localmente e envia apenas pelo cabeçalho ao host oficial. Não grava a chave no relatório.

`python coingecko_feed.py --check-key` faz uma consulta manual com a variável do terminal e permite tentar novamente sem aguardar o cache de erro. Não use em loop: cada validação consome uma chamada. Consultas automáticas continuam limitadas ao intervalo de 15 minutos. O relatório passa a registrar códigos seguros KEY_FORMAT, HTTP_401/403/429, CONNECTION ou INVALID_DATA, sem a URL/credencial da exceção. Falhas mantêm valores anteriores com aviso. Reinicie o iniciador para carregar uma nova versão do coletor e a chave do terminal atual.
