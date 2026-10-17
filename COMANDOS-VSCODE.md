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

As ordens permanecem simuladas. Uma validação reprovada bloqueia operações.
