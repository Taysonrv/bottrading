# Carteira compartilhada multipar — PAPER

Este experimento usa **20 USDT fictícios no total**, seis pares (BTC, ETH, SOL, BNB, XRP, DOGE), candles fechados de 15 minutos e no máximo uma posição ou reserva de compra. É independente da carteira antiga EMA/1h; não soma nem importa seu saldo.

Sinais EMA20/50 com filtro EMA200/ATR continuam sem validação de rentabilidade. Entre sinais recentes elegíveis, escolhe o menor spread, com desempate por nome. O teto por entrada é 6 USDT com taxa. Não força compras e ignora cruzamentos anteriores ao início do experimento.

## Iniciar tudo em um terminal

Encerre o iniciador antigo com Ctrl+C antes de iniciar este. Sua carteira antiga fica preservada; a nova sessão começa como outro experimento identificado.

```powershell
git pull --ff-only
.\.venv-spot\Scripts\python.exe -m unittest tests.test_portfolio tests.test_portfolio_run -v
.\.venv-spot\Scripts\python.exe operar.py --engine portfolio --start
```

Sem --start, operar.py apenas verifica. O código local de acesso é impresso no terminal. O painel **Terminal** mostra a carteira compartilhada e as últimas ordens/preenchimentos; as seções antigas continuam pertencendo aos experimentos antigos.

O supervisor multipar inicia somente motor e painel: o motor produz seu próprio radar, evitando um segundo coletor. Preços e filtros vêm da API pública Binance; nenhuma chave ou ordem real é usada. O PC e o processo precisam permanecer ligados.

## Contabilidade e proteção

- Um ledger SQLite com transações BEGIN IMMEDIATE serializa as reservas para todas as moedas. Reinício não emite novo capital.
- Reconciliação por preenchimentos verifica caixa, quantidade, custo, taxas e resultado realizado.
- Entradas exigem sinal com até 2 minutos, cotação com até 5 segundos, spread até 0,2%, filtros válidos e risco estimado até 1% do caixa quando sem posição.
- Stop 2%, alvo 4%; taxa 0,1% por lado e slippage 0,1% por lado são hipóteses, não taxas pessoais verificadas.
- Perda diária de 3% ou drawdown de 10% bloqueiam entradas com trava persistente. Reduções ainda podem ocorrer enquanto não houver STOP externo.
- Cotação posterior à reserva, latência mínima de 500ms, limite de 10% da quantidade exibida. O simulador exige liquidez para preencher tudo; não modela fila nem preenchimentos parciais. A reserva expira em 60s.
- Saídas usam bid com slippage adverso, inclusive gaps. Mínimos e falta de liquidez podem deixar inventário exposto.
- STOP externo impede compras **e vendas**, cancelando reservas; não liquida posições. As proteções são sintéticas e dependem do processo.
- Prazo fixo de 24h desde a criação do plano. Reiniciar preserva o prazo. Ao terminar cancela entrada pendente e preserva inventário; não há renovação automática.

Dados em reports/local/portfolio: paper.sqlite, plan.json, status.json e radar.json. Não editar nem apagar para contornar travas. Mudança na política/sinal/runner exige revisão explícita da identidade; não migra silenciosamente.

## Validação

Testes cobrem reserva concorrente entre moedas, troca de par depois da venda, replay idempotente, reinício, custos, liquidez insuficiente, expiração, STOP, gap e trava diária, integridade do ledger, seleção causal e leitura do painel. Esses testes validam software, não vantagem financeira. Telegram do motor multipar, continuidade ilimitada, testnet e execução real seguem pendentes.

## Disponibilidade do painel

A parada normal do motor deixa o painel próprio aberto para consulta (estado IDLE). Falha do painel marca o supervisor DEGRADED, mas não encerra a proteção sintética do motor. Não há reinício automático ilimitado de componentes.

Se o painel já estiver aberto separadamente, retome somente o motor com:

```powershell
.\.venv-spot\Scripts\python.exe operar.py --engine portfolio --execution-only --start
```

Esse modo não cria nem encerra o painel externo e não imprime um novo código de acesso. Continua respeitando STOP, prazo e identidade existentes. Ctrl+C encerra os processos próprios; nunca remove STOP automaticamente.

## Alertas do motor multipar

O iniciador atualizado coleta alertas em segundo plano, sem permitir que falhas de notificação interrompam ordens ou proteção. Credenciais TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID são lidas do ambiente; nunca são gravadas no repositório ou nos arquivos da fila.

- Compras e vendas: par, quantidade, preço, taxa; venda inclui resultado realizado após as duas taxas.
- Saúde: execução, erro, parada e falta de atualização; estados iguais não geram avisos contínuos.
- Primeiro uso: começa no ponto atual do ledger, sem reenviar operações antigas. Depois disso lê todos os preenchimentos novos, mesmo além dos últimos 100 do painel.
- Falha de envio preserva a fila. Um envio por ciclo de 10 segundos; o processo permanece independente da carteira.
- Entrega é ao menos uma vez: uma queda depois de o Telegram receber e antes da confirmação local pode repetir uma mensagem. Não há promessa de entrega exatamente uma vez.
- Estado em alerts-state.json e alerts-status.json dentro de reports/local/portfolio. Não apagar para contornar inconsistências; identidade ou histórico divergente suspendem alertas sem alterar trading.

Se o iniciador já estava rodando antes desta atualização, pode executar o coletor separado, sem reiniciar o motor:

```powershell
.\.configurar-telegram.ps1
.\.venv-spot\Scripts\python.exe portfolio_alerts.py --start
```

O script de configuração existente envia uma mensagem de teste. Sem credenciais, o coletor mantém apenas a fila local e não envia nada. Ao usar --data-dir, aponte para a mesma pasta de dados da simulação. Não inicie dois coletores para a mesma carteira; a trava alerts.lock evita duplicidade.
