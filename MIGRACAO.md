# Migração preservando evidência e proteções

Existem dois motores distintos: `spot-runs/ema20` tem risco e ledger próprios
dentro da pasta da sessão; `reports/local/portfolio` é a carteira multipar.
Nunca mover um deles supondo que seja o outro. Nunca apagar STOP ou SQLite.

## Pré-requisitos EMA

- Encerrar o processo EMA normalmente; status deve ser STOPPED.
- Ledger reconciliado, units zero e sem ordem ativa. Um status antigo não basta.
- Preservar STOP. Sua presença não impede arquivar; sua remoção exige revisão
  da causa e autorização de retomada, não faz parte do script.
- Guardar o commit/configuração antigos. Identidade de sessão não pode ser
  reescrita para fazer um estado antigo passar em código diferente.

```powershell
python scripts/archive_session.py --data-dir . --session ema20 --reason "Migração planejada ATR"
```

O script exige `sim`, mantém runner.lock adquirido durante todos os movimentos,
recusa exposição/ordem e grava registro com cada caminho movido. O lock fica no
diretório original para evitar a corrida entre liberar lock e renomear a pasta
no Windows. Uma falha parcial deixa registro MOVING para revisão; não reinicie.
Não move `portfolio/` nem o `spot-risk/` global de outros experimentos.

## Carteira multipar

Antes de mudar portfolio.py, portfolio_run.py ou selection.py, encerrar o
supervisor/motor, verificar que runner.lock está livre e reconciliar SQLite.
Arquivar **a pasta portfolio completa** com status, plan, SQLite, risco e
STOP local. Se houver posição ou ordem, preservar o motor e resolver exposição
primeiro; não zerar estado nem inventar liquidação. Arquivar não vende ativos.
O script EMA não executa essa migração. Uma nova sessão de carteira deverá ter
capital/prazo declarados explicitamente e nunca herdar métricas de outra sessão.

## Pós-migração / rollback

- Confirmar hash de código/config novo e aquecimento causal.
- Nova sessão não deve importar saldo, PnL ou validação da anterior.
- Validar primeiro ciclo e relatórios com idade recente.
- Rollback exige o código/config exatos do arquivo e nenhum novo trade.
  Se já houve novo trade, manter as sessões separadas e reconciliar, sem
  sobrescrever arquivos nem restaurar um saldo antigo por cima do atual.

O observador V3 é separado: `python -m v3_engine.live --data-dir . --hours 48`.
Ele não tem carteira, não abre ordens e não altera a sessão ativa. Seu STOP local
é `reports/local/v3-runs/STOP`; o STOP global também é respeitado.
