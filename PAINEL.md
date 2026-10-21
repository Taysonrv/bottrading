# Spot Lab — computador e celular

O painel é um aplicativo web local, responsivo. Não depende de pacotes Python externos e não publica dados na internet. Não é um aplicativo nativo de loja nem funciona offline. O computador executa o servidor e precisa permanecer ligado.

## Computador

Na pasta do bot, execute:

```powershell
python dashboard.py
```

Abra `http://127.0.0.1:8765` e digite o código mostrado naquele terminal. Cada inicialização gera um código novo; ele não é salvo. Não confunda o código do painel com chaves Binance ou token Telegram. O painel nunca solicita essas credenciais.

O código também pode ser definido por `SPOTLAB_ACCESS_CODE`, com pelo menos 12 caracteres, no ambiente local. Não coloque o código na URL nem em arquivos compartilhados.

## Celular na mesma rede Wi-Fi

Identifique o IPv4 privado do computador com `ipconfig` (por exemplo `192.168.1.10`). Encerre o painel anterior com Ctrl+C e execute, substituindo o exemplo pelo seu IP:

```powershell
python dashboard.py --lan-ip 192.168.1.10 --allow-lan-http
```

Abra `http://192.168.1.10:8765` no computador ou no navegador do celular e use o código exibido. A opção de rede usa HTTP sem criptografia: destina-se apenas a Wi-Fi privado confiável. Não exponha essa porta na internet nem use redes públicas. O programa não abre portas do roteador ou modifica o firewall. Se o Windows pedir acesso de rede, limite-o ao perfil privado.

Se o celular não conseguir conectar, confirme o IP, a mesma rede e as regras do firewall; redes de convidados podem impedir comunicação entre dispositivos. Este modo não dá acesso por 4G/5G fora de casa. Acesso remoto pela internet exige outra etapa com HTTPS e autenticação adequados.

## O que mostra

- Patrimônio simulado, resultado líquido, drawdown, custos e ordens, quando existir medição.
- Gráfico das medições realmente registradas, sem dados fictícios adicionados pelo painel.
- Últimos 50 eventos, sinais por ativo e estratégia, posições simuladas e pesquisa histórica.
- Atividade recente pelo `heartbeat.json` atualizado pelo bot. Sem heartbeat, não afirma que o processo está ativo.
- Indicação de validação ausente, vencida ou referente a outra versão do código.

As telas atualizam a cada dez segundos. O horário de cada fonte é exibido; relatórios antigos não se tornam cotações atuais ao abrir a página. Saldos reais da Binance e arquivos de credenciais não são servidos pelo painel.

A aba **Diagnóstico** explica separadamente as condições para observar sinais e para simular ordens. Uma validação reprovada bloqueia ordens, mas não impede observar; STOP impede ambos. Uma sessão de observação de outra versão exige arquivamento antes de iniciar outra. Nenhum diagnóstico remove travas ou inicia o bot. Ausência de heartbeat não comprova uma falha: confira se o painel aponta para a mesma pasta do processo.

A aba **Estratégias** também mostra a comparação de saída defensiva quando existir no relatório salvo, incluindo retorno, drawdown, vendas e exposição remanescente. A política permanece experimental e não adotada. Relatórios antigos sem essa comparação mostram um estado vazio, sem inventar valores.

O painel não inicia o observador nem o motor de simulação. Use outro terminal para `python bot.py watch` ou `python bot.py run`. Não execute os dois processos ao mesmo tempo. Após mudanças de código, siga o procedimento de arquivamento de observação em `COMANDOS-VSCODE.md`.

## Botão de desligar

O botão abre uma confirmação e, ao confirmar, cria o mesmo `STOP` usado pelo terminal. O processo em execução o reconhecerá antes da próxima ordem; não é garantia de cancelamento de uma ordem já em andamento e não liquida posições existentes. O painel permanece aberto para acompanhamento. Para retomar, revise o motivo e use o terminal; não há botão de compra, venda, resgate ou ativação real.

Login tem limitação de tentativas, sessão de oito horas e proteção de origem para comandos. A consulta aos relatórios e o STOP exigem sessão autenticada. O servidor só disponibiliza arquivos de interface previamente definidos. Use Ctrl+C no terminal do painel para encerrá-lo; isso não desliga o bot.

`--data-dir` permite apontar para uma pasta de dados existente. O STOP será gravado nessa pasta. Use somente uma instância de painel por pasta. Evite compartilhar a URL/código com outras pessoas: quem tiver acesso poderá consultar a simulação e acionar STOP.
# Painel aberto sem atividade

`python dashboard.py` inicia a interface. `python -m unittest -q` executa testes de código e termina; não inicia o acompanhamento do mercado.

Para acompanhar sinais, mantenha o painel em um terminal e abra outro terminal na mesma pasta:

```powershell
python bot.py observe
python bot.py watch
```

O primeiro comando confirma se a coleta funciona. Se indicar que a versão da sessão mudou, encerre qualquer observador antigo, execute `python bot.py observation-archive` para preservar o histórico e repita os comandos. STOP exige revisar a causa antes de qualquer retomada. O observador não gera ordens nem medições de patrimônio; coleta somente sinais de candles fechados. O mesmo candle não gera amostras duplicadas.

Para gerar uma medição de patrimônio, encerre o observador com Ctrl+C, execute `python bot.py once` e depois reinicie `python bot.py watch`. A validação permanece obrigatória para ordens. `python bot.py performance` apenas exporta a medição já salva.

A aba Estratégias também mostra o relatório das seis hipóteses diárias em `reports/2026-10-18-daily-results.json`. É um resultado salvo, separado da validação ativa. Para repetir a pesquisa use `python daily_research.py`; o painel lê os resultados na próxima atualização. Reinicie o painel e atualize a página após instalar mudanças do GitHub.



## EMA/ATR ao vivo

A aba **EMA/ATR ao vivo** acompanha a sessão `ema20`, separada da sessão anterior. Lê `reports/local/spot-runs/ema20/status.json` e o ledger SQLite em modo somente leitura. Exibe patrimônio, realizado, taxas, caixa livre/reservado, distribuição, posição, stop/alvo, últimas 100 ordens e últimos 100 preenchimentos. Zero operações é mostrado como zero, sem inventar negócios. Não há gráfico histórico de patrimônio desta sessão porque ainda não existe série histórica persistida de marcações.

Atualização automática a cada 10 segundos. Relatório com mais de 60 segundos é antigo; ERROR e STOPPED não aparecem como coleta saudável. Se o ledger mudou antes do status, o patrimônio fica temporariamente indisponível até a próxima atualização. STOP do painel é global e afeta também a outra simulação; não liquida posições. Esta aba não inicia processos nem altera a estratégia.


A aba **Diagnóstico** também mostra a saúde da EMA/ATR: idade da medição, último sinal, STOP, perda diária, drawdown, ordem pendente e inventário protegido. Os limites são lidos do checkpoint persistido em modo somente leitura; indisponibilidade não é apresentada como risco liberado. O checkpoint tem horário próprio e não é combinado com a carteira como se fosse uma transação única. O cabeçalho do diagnóstico usa a sessão EMA quando ela está disponível; a sessão anterior permanece identificada abaixo.
