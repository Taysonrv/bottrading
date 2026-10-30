# Guardião externo no Windows

`session_guard.py` lê plano e relatórios da sessão existente. Não cria sessão, carteira ou ordem e nunca inicia o motor de trading. Com porta fechada, recupera somente o painel se o supervisor perdeu confirmação ou se a interface ficou ausente por120s mesmo com supervisor vivo, até três tentativas externas. Isso cobre também o esgotamento da recuperação interna. Uma solicitação local recente `reports/local/panel-refresh.json` com `requested_ms` permite a atualização planejada sem aguardar120s; é consumida uma vez e não ignora STOP/prazo. Motor sem relatório recente exige revisão. Porta aberta não prova saúde HTTP: o diagnóstico do painel continua necessário.

```powershell
.\install-session-guard.ps1 -DataDir CAMINHO_DA_SESSAO -Port 8769
```

A tarefa `SpotLab-Guard-NOME_DA_SESSAO` roda com permissões limitadas do usuário conectado. Tem gatilhos de início e login, ignora instâncias simultâneas e até três reinícios em falha do guardião. Não pede senha, não instala um serviço como administrador, não desativa suspensão nem acorda a máquina. Ao atingir STOP, prazo, plano inválido ou relógio sem confirmação, o guardião encerra. Um login após o prazo não renova nada.

O painel apresenta o estado do guardião com verificação de idade. `reports/local/external-guard.json` guarda tentativas e estado; eventos entram no diário operacional. Se o guardião também morrer, o último relatório fica antigo, não é prova de atividade.

Recuperação externa do painel usa `SPOTLAB_ACCESS_CODE` se disponível no ambiente da tarefa; caso contrário gera novo código local. Ele fica em `reports/local/external-panel.log`. Não são usadas chaves da Binance. Não publicar esse log ou informações locais de acesso.

Essa versão melhora a observabilidade fora do supervisor, mas não oferece disponibilidade com usuário desconectado, PC desligado ou dormindo. Para isso, uma VPS/serviço dedicado requer configuração posterior. Engine interrompido ou posição sem proteção sintética continuam exigindo intervenção; nenhuma retomada automática ignora risco.

Para remover somente o guardião, use o Agendador de Tarefas do Windows para parar e excluir a tarefa. Isso não encerra o motor, não vende posições e não remove STOP. A tarefa é específica da sessão e pode ser removida após seu encerramento.
