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

`validate` baixa por paginação 365 dias de candles horários fechados por par (configurável entre 180 e 1095 dias). Rejeita lacunas, dados incompletos e preços inválidos. Compara três regras fixas: `regime_v1` (original), `trend_v1` (tendência por médias) e `breakout_v1` (proximidade de máxima anterior em tendência de alta). Não ajusta parâmetros nem escolhe uma estratégia automaticamente.

Após 200 candles de aquecimento, os primeiros 75% são divididos em três janelas; os 25% finais ficam separados para avaliação. Também testa o período final com taxas e slippage dobrados. Todos os períodos começam com 1.000 USDT fictícios e sem posições. O benchmark principal é comprar e manter com 100% do capital (pesos iguais na carteira); o JSON também mostra um benchmark proporcional à exposição permitida. Cada janela deve superar o benchmark e zero, ter pelo menos três operações e drawdown inferior a 15%. A aprovação exige passar individualmente e na carteira conjunta, incluindo o cenário de custos dobrados.

O backtest usa sinais do fechamento anterior e execução na abertura seguinte. Aplica os mesmos limites de exposição e tamanho de ordem da simulação. Verifica também uma estimativa conservadora de perda pelas mínimas horárias simultâneas. Taxas são debitadas do caixa; slippage altera o preço de execução. Posições restantes são avaliadas pelo valor líquido estimado de venda ao final. O mínimo genérico de 10 USDT não substitui filtros reais da exchange.

O resultado está em `research-report.md` e o detalhamento em `validation.json`. A estratégia ativa permanece definida em `config.json`; nenhuma comparação altera essa configuração. A aprovação expira em 24 horas e alterações no código/configuração a invalidam. Reexecute a validação manualmente. Reutilizar o período final para ajustar regras exige um novo período futuro para confirmação independente.

`run` verifica o mercado a cada minuto e decide apenas uma vez por candle fechado. O sinal usa candles fechados, mas a execução simulada consulta o bid/ask atual: compra no ask e vende no bid, mais slippage estimado. O computador precisa permanecer ligado, com internet e processo aberto. Nenhum serviço ou tarefa agendada foi instalado.

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

`python bot.py review` resume eventos das últimas 24 horas em `night-review.json` e mostra quais estratégias/ativos reprovaram na última comparação. No processo contínuo, há uma revisão na primeira execução de cada dia no fuso UTC-3. Não baixa dados nem executa novas pesquisas automaticamente. Ainda não gera alterações de código; nunca modifica parâmetros sozinho.

`events.jsonl`: diário; `state.json`: carteira simulada e maior patrimônio; `validation.json`: resultados por janela; `STOP`: trava local.

## Limitações e próximos passos

Ainda faltam modelo de liquidez/profundidade, precisão e filtros de cada par, apuração de lucro realizado por operação, monitoramento de quedas do processo e reconciliação. O backtest não dispõe de spread histórico real nem latência; usa slippage configurável. A carteira histórica inicia sem posições, portanto não valida a liquidação das suas posições preexistentes. O histórico de um ano e a comparação de regras são pesquisa preliminar, não comprovação de rentabilidade. Não há treinamento ou otimização de parâmetros.

A integração privada, importação de todos os ativos Spot, filtros de quantidade/notional, recuperação de ordens e operação real não estão implementadas. Não forneça uma chave Binance para este protótipo. A autorização para vender ativos será aplicada somente numa etapa posterior, após revisão da carteira e autorização de ativação real.

Os comandos `run` e `once` compartilham trava exclusiva no Windows, impedindo execução simultânea. Não execute duas validações simultaneamente.

## Referências oficiais

- [Binance Spot: documentação](https://github.com/binance/binance-spot-api-docs)
- [Binance: dados de mercado](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market)
- [Telegram: sendMessage](https://core.telegram.org/bots/api#sendmessage)
