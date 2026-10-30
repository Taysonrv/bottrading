# Execução sem CMD aberto

O bot não exige terminal do VS Code ou janela CMD visível quando iniciado pelo lançador de segundo plano. Isso não o transforma em serviço de servidor: o PC precisa estar ligado, acordado, com internet e usuário conectado. Fechar o navegador não desliga o motor.

O guardião do Windows usa `pythonw.exe`. Filhos do supervisor usam `CREATE_NO_WINDOW` no Windows. Não há janela interativa necessária para painel, radar ou execução.

## Próxima sessão, início explícito

Depois de conferir encerramento da sessão anterior, inventário e STOP:

```powershell
.\iniciar-segundo-plano.ps1 -DataDir reports/local/forward12-NOVA-SESSAO -Port 8769
```

O diretório precisa ter sido preparado previamente. O script verifica porta, prazo e travas antes de registrar uma tarefa limitada ao usuário atual. Não sobrescreve uma tarefa existente. Não possui gatilho de login, retry do motor ou renovação automática. O supervisor preserva a sessão existente quando válida; uma sessão nova recebe seu próprio plano de 24h. O limite de 25h da tarefa é apenas um teto operacional e não estende o prazo de trading.

O início é solicitado, não prova de sucesso: confirme a carteira e RUNNING no painel. O código local de acesso está no log `reports/local/system-dashboard.log` da sessão; não publique esse log. Para cada sessão, o guardião externo precisa ser registrado separadamente após existir o plano.

O botão STOP bloqueia operações conforme as regras existentes; não garante venda imediata. Não encerrar a tarefa pelo Agendador enquanto houver posição sem antes revisar a proteção sintética. Fechar CMD é diferente de desligar PC, suspender ou sair da conta do Windows.
