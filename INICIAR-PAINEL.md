# Um terminal para o Spot Lab

Atualize o projeto e execute na pasta do bot:

```powershell
git pull
python iniciar.py
```

Inicia a simulação de 20 USDT fictícios, o coletor público e o painel em http://127.0.0.1:8768/. Não inicia bot.py watch, não importa saldo real e não envia ordens reais. Requer Python e Node.js 24+. O código de acesso aparece neste mesmo terminal e no log local do painel; não compartilhe o código ou o log.

Mantenha apenas esse terminal aberto. Ctrl+C encerra somente os processos criados pelo iniciador. O saldo e o histórico são preservados; uma interrupção pode deixar a última medição anterior à parada. O painel ficará indisponível após a parada. Falha ou término de um componente encerra os outros, sem reinício automático.

Antes da primeira execução, encerre os processos antigos pelos terminais que os iniciaram usando Ctrl+C. O iniciador recusa porta ocupada, processo paper já ativo, trava do coletor, STOP, drawdown travado ou sessão expirada. Não mata processos preexistentes, não apaga relatórios nem reinicia o saldo. Uma sessão existente continua somente até seu término original. Não remova uma trava de coletor sem conferir se ele está ativo.

Verificação sem iniciar: `python iniciar.py --check`. Outra porta: `python iniciar.py --port 8769`. Não execute junto com outros iniciadores na mesma pasta. Logs privados ficam em `reports/local/launcher-*.log`, ignorados pelo Git.

O mesmo terminal mostra a última compra/venda, patrimônio estimado e resultado realizado quando há nova ordem, mudança de saúde ou a cada cinco minutos. Medições com 180 segundos ou mais são sinalizadas como antigas. Um processo vivo não garante cotação atualizada. Esses avisos não alteram a estratégia nem enviam notificações ao Telegram.

## Explorer simplificado

O VS Code exibe os pontos de entrada iniciar.py, dashboard.py e bot.py, os arquivos de configuração e os assets do painel. Módulos internos, testes, logs e documentos de pesquisa são ocultados pelo arquivo .vscode/settings.json, sem apagar ou mover nada. Para voltar a exibi-los, desative as entradas de files.exclude nas configurações do workspace. A tarefa “Spot Lab: iniciar tudo (20 USDT fictícios)” também inicia todos os componentes em um terminal.

## Telegram no mesmo terminal

Interrompa o iniciador com Ctrl+C e execute:

```powershell
git pull
.\configurar-telegram.ps1
python iniciar.py
```

O script pede o token oculto e o chat ID localmente e envia uma mensagem de teste. Não envie essas credenciais no chat. Se o teste falhar, confira a configuração antes de iniciar. O iniciador herda essas variáveis somente desse terminal, sem salvá-las em arquivo. Sem as duas variáveis, Telegram fica desativado e a simulação continua.

O relé lê o relatório a cada dez segundos em uma thread separada, sem bloquear decisões de trading. Envia novas compras/vendas fictícias e mudanças de estado (dados antigos, erro, STOP ou drawdown). Na primeira configuração ignora as ordens anteriores; nos reinícios preserva os identificadores enviados em reports/local/paper-alerts.json. Envio recusado é tentado novamente. Uma interrupção entre o envio e a gravação da confirmação pode causar repetição; não há garantia de entrega única. Não apague o estado para resolver falhas. Não há resumo diário automático nesta versão. Ao fechar o iniciador os avisos também param.

## Diagnosticar coleta

Se aparecer “Simulação erro”, execute `python diagnosticar.py` em outro terminal. Ele consulta horário, bid/ask e 60 candles horários públicos do par da posição (BTCUSDT se não houver posição). Salva reports/local/connection-diagnostic.json, sem alterar saldo, histórico ou STOP. Um diagnóstico posterior positivo não prova qual foi a falha anterior e não verifica todos os pares do universo. Não execute loops de reinício para tentar forçar operações.


## Encerramento e resumo preservado

Ao terminar o prazo da sessão, o iniciador reconhece a saída normal do simulador e encerra os componentes que iniciou. Ctrl+C também encerra o conjunto. STOP continua sendo um bloqueio de ordens; não liquida posições.

Após encerrar os processos, salva um resumo único em `reports/local/session-summaries/`, em JSON e Markdown. O motivo distingue prazo concluído (`deadline`), STOP (`stop`), interrupção (`interrupted`) e falha (`failure`). Saídas inesperadas continuam sendo tratadas como erro.

O resumo usa a última medição salva, sem obter um preço de liquidação e sem reiniciar saldo ou histórico. Uma interrupção não significa que o teste foi concluído. Se a auditoria falhar, o iniciador avisa; use `python auditar.py` para revisar o estado preservado. Uma sessão cujo prazo terminou exige revisão antes de outra sessão.


## Integridade dos resultados

A auditoria também rejeita ordens e medições com horários futuros, curva posterior à última medição, posição com formato inválido e caixa reconstruído negativo. Sem posição aberta, o patrimônio deve corresponder ao caixa; uma posição não pode ter valor marcado negativo.

Essas verificações conferem o histórico salvo sem alterar operações ou saldo. Uma reconciliação positiva não confirma o preço de mercado da posição, não prova vantagem da estratégia e não libera negociação real. Divergências aparecem em `issues` no JSON e nas limitações do relatório Markdown.


## Consulta rápida sem abrir outro painel

Execute `python runtime_status.py` na pasta do projeto para ler o último relatório salvo, sem iniciar processos ou consultar APIs. O mesmo resumo é exibido pelo iniciador: patrimônio, resultado realizado, última ordem, par da posição aberta, contagem de compras/vendas no histórico retido e idade da medição em segundos. Vendas parciais contam como vendas, não como ciclos completos. A idade da medição não comprova a atualidade de cada cotação.

Quando o prazo foi atingido, o resumo pede conferir o encerramento e o relatório; isso não confirma que o processo já terminou. STOP e drawdown continuam tendo prioridade no aviso. Dados inválidos são apresentados como indisponíveis. A mudança da idade a cada segundo não dispara mensagens adicionais de estado no Telegram.
