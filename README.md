# Binance Spot Bot

**Interface para computador e celular:** execute `python dashboard.py` e siga [PAINEL.md](PAINEL.md). O painel local mostra os relatórios e permite acionar STOP com login. Não habilita operações reais.

[Prévia no computador](docs/panel-desktop.png) · [Prévia no celular](docs/panel-mobile.png)

Protótipo em Python para simulação de estratégias Binance Spot. Não envia ordens reais nem acessa a carteira Binance.

Inclui regimes de mercado, bloqueio de drawdown, desligamento local, validação cronológica e notificações Telegram opcionais. A pesquisa compara três regras fixas em um ano de dados, com período final separado, carteira conjunta e custos dobrados. A simulação usa bid/ask atual; o backtest executa na abertura seguinte ao sinal.

O cálculo de tamanho das ordens é compartilhado pelo backtest e pela simulação, incluindo custos no orçamento e nos limites de exposição. A aprovação também considera carteira inicialmente investida e execução contínua sem reiniciar saldos entre janelas.

Leia [as instruções e limitações](LEIA-ME.md) antes de executar.

```powershell
python -m unittest -v
python bot.py validate
python bot.py once
```

No VS Code, use **Terminal → Executar Tarefa** para testar, validar, simular ou desligar. Não execute tarefas que alteram estado simultaneamente.

Os arquivos de estado, resultados e credenciais ficam fora do controle de versão. A configuração inicial contém apenas valores fictícios.

Após `validate`, abra `research-report.md` para o resumo legível. Nenhuma estratégia é selecionada automaticamente; aprovação exige superar comprar e manter em todas as janelas, inclusive na carteira.

Para coletar sinais futuros sem criar ordens, use `python bot.py observe` ou mantenha `python bot.py watch` aberto. Consulte `observation-report.md`. Esse diário separado não libera estratégias reprovadas. Configure Telegram localmente com `./configurar-telegram.ps1`; o token não é salvo em arquivo.

Para visualizar a carteira Spot, use `./configurar-binance-leitura.ps1` com chave HMAC somente leitura. A consulta gera relatórios locais ignorados pelo Git. Não altera a carteira, não importa posições automaticamente e não habilita ordens reais.

Após um ciclo de simulação, `python bot.py performance` gera o relatório de caixa, patrimônio, lucro realizado, resultado não realizado e custos estimados. Posições preexistentes são avaliadas pelo preço no início da medição; não se inventa seu custo histórico de compra.
