# Comandos no terminal PowerShell do VS Code

Abra a pasta local:

```powershell
code "C:\Users\Tayson\Documents\Codex\2026-10-16\ess\outputs\binance-bot"
```

No terminal integrado, use:

```powershell
python -m unittest -v
python bot.py validate
python bot.py once
```

Para manter a simulação rodando:

```powershell
python bot.py run
```

Para desligar, em outro terminal:

```powershell
python bot.py stop
```

Também estão disponíveis em **Terminal → Executar Tarefa**.

Para acompanhar sinais novos sem criar ordens ou alterar a carteira simulada:

```powershell
python bot.py observe
python bot.py watch
```

`observe` registra uma amostra; `watch` mantém o acompanhamento aberto. Abra `observation-report.md` para ver o resumo. Resultados começam a aparecer após observações consecutivas em horas diferentes. O processo deve permanecer ligado.

Como alternativa no Windows, `./iniciar-observacao.ps1` inicia `watch` em segundo plano, com janela oculta e saída nos arquivos `watch-output.log` e `watch-error.log`. Não cria tarefa de inicialização e não reinicia após desligar o computador. Use somente uma das opções: terminal aberto ou segundo plano.

Para consultar o estado salvo:

```powershell
python bot.py status
```

Para configurar notificações somente no terminal atual (token oculto na digitação):

```powershell
.\configurar-telegram.ps1
python bot.py watch
```

É necessário criar previamente um bot no BotFather e obter o chat ID da sua conversa. O script envia uma mensagem de teste ao chat informado. Nenhuma credencial é salva. Se a política do PowerShell bloquear o script, não altere a política automaticamente: use a configuração de ambiente aprovada no seu computador.

As ordens permanecem simuladas. Uma validação reprovada bloqueia operações.
