# Revisão da carteira compartilhada PAPER

Na pasta do projeto que contém os dados da sessão:

```powershell
python session_audit.py --data-dir .
```

O comando imprime JSON. Para guardar uma cópia, redirecione a saída para um arquivo novo. Não sobrescreva ledger, plano, STOP ou relatórios do motor. Se o código e os dados estiverem em pastas distintas, informe a pasta dos dados em --data-dir.

O relatório usa o ledger completo reconciliado da carteira compartilhada, sem somar experimentos EMA ou mocks. Apresenta saldo, taxas, resultado realizado, ordens por estado, cancelamentos por motivo, preenchimentos, exposição existente e saúde dos componentes. Não envia notificações ou ordens e não inicia processos.

Sem inventário, o caixa reconciliado permite conhecer o patrimônio sem cotação. Com posição aberta, só aceita marcação recente compatível com os mesmos dados da carteira; caso contrário o patrimônio fica desconhecido. Leituras de serviços diferentes não constituem uma transação atômica entre processos.

Os intervalos desconhecidos do monitor não são uptime. A janela do monitor pode incluir sessões anteriores e não equivale à duração da sessão da carteira. Telegram configurado em relatório antigo não é entrega atual confirmada.

Ausência de plano válido deixa o vencimento desconhecido, em vez de indicar falsamente que a sessão ainda está no prazo. STOP é apenas lido e nunca removido. O relatório não reinicia prazo ou saldo.

O veredito é NOT_READY_FOR_LIVE neste estágio do projeto. Este relatório operacional não é um mecanismo de aprovação estatística e não pode promover uma estratégia para live. Zero PnL sem preenchimentos não demonstra vantagem.

Testes:

```powershell
python -m unittest tests.test_shared_review -v
```

Cobrem ausência de dados sem criação de arquivos, caixa sem quote, preservação dos arquivos da carteira, intervalo desconhecido, Telegram antigo e horário inválido.
