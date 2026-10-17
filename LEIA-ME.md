# Bot Binance Spot — protótipo em simulação

Este pacote não envia ordens reais e não acessa sua conta. Usa Python 3.11+ e apenas a biblioteca padrão. O saldo inicial de 1.000 USDT é fictício. BTC e ETH são os pares iniciais de desenvolvimento, não recomendações de investimento.

## Usar no Windows

Abra o PowerShell na pasta deste arquivo:

```powershell
python -m unittest -v
python bot.py validate
python bot.py once
python bot.py run
```

`validate` consulta até 1.000 candles horários fechados por par e testa regras fixas em três janelas cronológicas, depois do aquecimento. O benchmark é comprar e manter o respectivo ativo. Cada janela deve superar o benchmark e zero, ter pelo menos três operações e drawdown inferior a 15%. Taxas e slippage são estimados, configuráveis. A aprovação expira em 24 horas e qualquer alteração no código/configuração a invalida. Reexecute a validação manualmente; o bot não flexibiliza os critérios quando reprovado.

`run` verifica o mercado a cada minuto e decide apenas uma vez por candle fechado. O computador precisa permanecer ligado, com internet e processo aberto. Nenhum serviço ou tarefa agendada foi instalado.

## Desligar

Em outro PowerShell na mesma pasta:

```powershell
python bot.py stop
```

Isso cria o arquivo `STOP`, verificado antes de cada ordem simulada. Não vende posições automaticamente. `python bot.py resume` remove esse arquivo, mas não remove uma trava de drawdown já acionada. Essa trava fica persistida em `state.json` e exige revisão manual. Os 15% são um gatilho de bloqueio, não uma garantia de perda máxima: posições existentes continuam expostas.

## Carteira fictícia

Edite `config.json` antes da primeira execução. `paper_usdt` representa USDT livre. Em `paper_positions`, informe quantidades, por exemplo `{"BTCUSDT": 0.001}`. Todo par com posição precisa constar em `symbols`. O protótipo não importa saldos e não converte ativos automaticamente; só representa posições que você cadastrar. Não reinicie `state.json` para esconder perdas ou liberar uma estratégia reprovada.

Limites iniciais de desenvolvimento: 5% do patrimônio por ordem, alvo de 20% por ativo e até 60% de exposição total. Não constituem perfil de risco aprovado para operação real. Vendas de posições preexistentes também estão sujeitas ao teste de validação; reprovação congela operações daquele par.

## Telegram

Crie um bot com o [BotFather](https://t.me/BotFather), inicie uma conversa com ele e configure localmente as variáveis de ambiente `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` no PowerShell que executará o processo. Não coloque o token em mensagens, código ou arquivos compartilhados. Sem essas variáveis, os eventos ficam apenas no terminal e no diário.

São enviados eventos de início/fim, ordens simuladas, bloqueios, validação, erros e revisão diária. O envio ainda não foi testado com uma conta Telegram. Não há comandos remotos nem botão Telegram nesta versão; o desligamento é local.

## Revisão e arquivos

`python bot.py review` resume eventos das últimas 24 horas em `night-review.json`. No processo contínuo, há uma revisão na primeira execução de cada dia no fuso UTC-3. Este é um resumo básico, com sugestão genérica de investigação; ainda não otimiza estratégias nem produz melhorias testadas. Nunca modifica código ou parâmetros sozinho.

`events.jsonl`: diário; `state.json`: carteira simulada e maior patrimônio; `validation.json`: resultados por janela; `STOP`: trava local.

## Limitações e próximos passos

O backtest curto serve apenas como triagem. Ainda faltam histórico de anos, modelo de liquidez, cotações executáveis em tempo real, apuração de lucro por operação, comparação de carteira completa, monitoramento de quedas do processo e reconciliação. A execução simulada usa o último fechamento conhecido, enquanto o backtest usa o fechamento seguinte ao sinal; ambos precisam ser substituídos por um modelo de execução mais realista antes de concluir sobre desempenho. Não há seleção/ajuste de parâmetros por treinamento, apenas teste de regras fixas em janelas sucessivas.

A integração privada, importação de todos os ativos Spot, filtros de quantidade/notional, recuperação de ordens e operação real não estão implementadas. Não forneça uma chave Binance para este protótipo. A autorização para vender ativos será aplicada somente numa etapa posterior, após revisão da carteira e autorização de ativação real.

Execute somente um processo que modifica estado por vez. O comando `run` usa trava exclusiva no Windows; não execute `once` simultaneamente.

## Referências oficiais

- [Binance Spot: documentação](https://github.com/binance/binance-spot-api-docs)
- [Binance: dados de mercado](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market)
- [Telegram: sendMessage](https://core.telegram.org/bots/api#sendmessage)
