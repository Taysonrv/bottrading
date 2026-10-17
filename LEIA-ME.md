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

O dimensionamento é compartilhado em `execution.py`: o orçamento por ordem inclui a taxa e o preço com slippage. Na compra, o spread bid/ask e a redução de patrimônio pelos custos entram no cálculo de exposição máxima após a operação. Posições já acima dos limites não recebem mais compras; a redução permanece sujeita ao limite por ordem. Isso não garante que oscilações de preço mantenham a exposição abaixo do limite.

A validação também exige aprovação em dois cenários de carteira: período final iniciando com 80% do capital em cripto, com pesos iguais, e todo o período sem reiniciar caixa/posições. No cenário de posições existentes, 80% é um teste fixo de robustez, não recomendação nem leitura da sua carteira. O cenário não cobra uma compra fictícia inicial, pois os ativos já são considerados existentes no começo; o resultado começa nesse preço de referência.

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

Execute `./configurar-telegram.ps1` no PowerShell para informar token com digitação oculta e chat ID. O script define variáveis somente no terminal atual e envia um teste. As mensagens são legíveis; bloqueios e erros idênticos são enviados no máximo uma vez por dia, salvo falha no envio. Ordens e eventos de início/fim nunca são suprimidos. Amostras de observação não enviam alerta a cada minuto.

## Acompanhamento de sinais futuros

`python bot.py observe` registra uma amostra de sinais das três estratégias. `python bot.py watch` mantém esse acompanhamento a cada minuto, com uma única amostra por candle horário fechado. Usa apenas dados públicos e não chama o motor de ordens nem altera `state.json`. Funciona mesmo com estratégias reprovadas porque apenas observa sinais, sem simular compras ou vendas.

O diário separado `observation-state.json` preserva sinais, horário e bid/ask coletados naquele momento. Na amostra da hora seguinte, associa o retorno bruto do mercado ao sinal anterior. Intervalos com lacunas ou fora da faixa de 45–75 minutos são ignorados, sem preenchimento retroativo. `observation-report.md` apresenta as médias desses retornos após sinais de entrada: não são lucro, não incluem custos e não aprovam estratégias.

Mudanças no código/configuração interrompem uma sessão de observação existente. Preserve os dois arquivos de observação em uma pasta de arquivo e inicie uma nova sessão somente após revisar a mudança; não misture resultados entre versões. `STOP` desliga também o acompanhamento. `run`, `once`, `watch` e `observe` compartilham a mesma trava de processo.

`python bot.py status` consulta o estado salvo sem rede. Não confirma que um processo esteja rodando. Nenhum acompanhamento contínuo é iniciado automaticamente pela instalação.

No Windows, `./iniciar-observacao.ps1` permite iniciar manualmente o acompanhamento em segundo plano, com janela oculta. Logs ficam em `watch-output.log` e `watch-error.log`, ignorados pelo Git. O script não configura inicialização automática nem reinicia o processo após falhas. Use `python bot.py stop` para desligar. Credenciais Telegram precisam estar no mesmo terminal que inicia o script.

## Revisão e arquivos

`python bot.py review` resume eventos das últimas 24 horas em `night-review.json` e mostra quais estratégias/ativos reprovaram na última comparação. No processo contínuo, há uma revisão na primeira execução de cada dia no fuso UTC-3. Não baixa dados nem executa novas pesquisas automaticamente. Ainda não gera alterações de código; nunca modifica parâmetros sozinho.

`events.jsonl`: diário; `state.json`: carteira simulada e maior patrimônio; `validation.json`: resultados por janela; `STOP`: trava local.

## Limitações e próximos passos

Ainda faltam modelo de liquidez/profundidade, precisão e filtros de cada par, apuração de lucro realizado por operação, monitoramento de quedas do processo e reconciliação. O backtest não dispõe de spread histórico real nem latência; usa slippage configurável. A carteira histórica inicia sem posições, portanto não valida a liquidação das suas posições preexistentes. O histórico de um ano e a comparação de regras são pesquisa preliminar, não comprovação de rentabilidade. Não há treinamento ou otimização de parâmetros.

A consulta privada somente leitura está disponível via `python bot.py wallet-preview`; a importação automática para a simulação, filtros completos de execução, recuperação de ordens e operação real não estão implementados. A autorização para vender ativos será aplicada somente numa etapa posterior, após revisão da carteira e autorização de ativação real.

## Consultar sua carteira Spot

Execute `./configurar-binance-leitura.ps1` para informar localmente uma chave HMAC da Binance com somente leitura. Deixe trading e saques desabilitados. O script recebe chave e segredo com digitação oculta e define `BINANCE_API_KEY`/`BINANCE_API_SECRET` apenas no terminal atual, sem salvar credenciais. Se sua chave for RSA/Ed25519, este cliente HMAC não a suporta.

O cliente permite somente GET de hora do servidor, conta Spot, informações de pares e book ticker. Recusa endpoints de ordens e saques e não segue redirecionamentos. O horário é sincronizado com a Binance para assinar a consulta da conta. Mensagens de erro não exibem chaves ou URLs assinadas.

`wallet-preview.md` e `wallet-preview.json` mostram saldos livres/bloqueados e estimativas pelo bid em USDT. A proposta de capital inclui USDT livre e quantidades livres de moedas com par direto Spot/USDT em negociação. Saldos bloqueados, moedas sem cotação e pares suspensos são listados separadamente e não entram na proposta. Não há conversão automática por pares intermediários. Ativos abaixo do mínimo estimado são marcados como possíveis resíduos; não se garante execução.

Esses relatórios contêm dados financeiros: ficam locais, ignorados pelo Git, e não são enviados ao Telegram. A consulta não altera `config.json`, `state.json` ou posições na Binance. Sem credenciais configuradas, o comando se recusa a conectar. A integração autenticada precisa ser validada com sua chave de leitura; os testes automatizados usam dados fictícios. O relatório pode ficar desatualizado após movimentações na conta.

O diagnóstico distingue marcadores LD sem par Spot, pares suspensos, ativos sem par direto e falta de cotação. O prefixo LD é um indício para conferir o Earn, não prova da disponibilidade para resgate. Nenhum marcador é convertido em moeda Spot apenas removendo o prefixo. Se não houver capital livre com cotação, `capital_ready` será falso; a consulta não substitui esse saldo por dinheiro fictício nem cria uma carteira aprovada. Para usar recursos do Earn, faça você mesmo o resgate na Binance e gere novamente `python bot.py wallet-preview` após confirmar os saldos livres. O programa não tem endpoints de resgate ou transferência.

Os comandos `run` e `once` compartilham trava exclusiva no Windows, impedindo execução simultânea. Não execute duas validações simultaneamente.

## Contabilidade da simulação

`python bot.py performance` gera `performance-report.md` a partir da última medição salva, sem rede. Execute um ciclo para atualizar a medição. A contabilidade usa custo médio e inclui taxas na compra e na venda. Slippage já afeta preços e não é subtraído duas vezes. O resultado não realizado considera custos estimados de venda das posições restantes, sem criar ordens de encerramento.

Para posições já existentes ou arquivos antigos sem contabilidade, a primeira medição usa o bid como valor inicial. Não representa preço histórico de compra nem reconstrói operações anteriores à migração. O maior patrimônio e a trava de drawdown são preservados. Inconsistência entre caixa, posições e resultados bloqueia a execução; não edite os saldos manualmente depois de iniciar a medição. O relatório distingue custos pagos de estimativas de liquidação.

Ao atualizar o código durante uma observação, encerre o processo com `python bot.py stop`. Aguarde o término, execute `python bot.py observation-archive` para preservar a sessão anterior, depois `python bot.py resume` e `python bot.py watch`. O arquivo da carteira simulada não é reiniciado. A sessão arquivada fica local, fora do Git. A aprovação histórica anterior também expira após mudanças de código.

## Referências oficiais

- [Binance Spot: documentação](https://github.com/binance/binance-spot-api-docs)
- [Binance: dados de mercado](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market)
- [Telegram: sendMessage](https://core.telegram.org/bots/api#sendmessage)
