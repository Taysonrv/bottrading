# Próxima versão PAPER: doze pares, uma carteira

A versão `PAPER12_V1` aceita BTC, ETH, SOL, BNB, XRP, DOGE, ADA, LINK, AVAX, LTC, DOT e NEAR contra USDT. Mantém EMA/ATR 15m, orçamento por entrada até 6 USDT, capital total 20 USDT, uma posição/reserva, taxa e slippage hipotéticos de 0,1% por lado, stop 2%, alvo 4%, limite diário 3% e drawdown 10%. Mais pares não garantem mais preenchimentos ou lucro.

O ledger e runner desta versão estão congelados separadamente em `portfolio12.py` e `portfolio12_run.py`, derivados da implementação de seis pares. A duplicação é deliberada para manter a identidade da sessão antiga intacta; correções futuras nos dois motores exigem revisão e testes explícitos. O novo ledger inclui hashes do runner, scanner, sinais, configuração, risco, seleção e execução compartilhados. Mudança nessas fontes exige outra versão/sessão, não migração automática.

`portfolio_backend.py` seleciona o novo ledger somente quando existe um marcador exato `portfolio12.json`. Marcador inválido bloqueia leitura/execução; nunca tenta reinterpretar uma carteira antiga. O painel, alertas, relatório e diagnóstico usam a mesma seleção. O supervisor continua sendo `operar.py --engine portfolio`, escolhendo o runner adequado ao perfil.

## Preparar sem iniciar

```powershell
python -m prepare_portfolio12 --data-dir reports/local/forward12-NOVA-SESSAO
```

Isso não emite capital, não cria SQLite e não inicia ordens. O caminho deve ser novo. Os dois arquivos copiados para `spot_engine/` são metadados exigidos pelo preflight legado; o código executável permanece na instalação versionada do projeto.

Depois de encerrar e preservar a sessão anterior, revisar posições/ordens remanescentes e selecionar explicitamente a nova sessão:

```powershell
python operar.py --engine portfolio --data-dir reports/local/forward12-NOVA-SESSAO --port 8769 --start
```

O comando cria um experimento independente de até 24h. Não iniciar ao mesmo tempo que outra carteira experimental de 20 USDT como se houvesse capital compartilhado entre elas. O novo saldo fictício não representa recuperação da perda antiga; resultados ficam separados e devem incluir todas as tentativas. Sem renovar automaticamente ou promover a dinheiro real.

O guardião externo precisa ser registrado para cada nova sessão, respeitando seu próprio prazo. Até a ativação explícita da próxima sessão, a execução continua nos seis pares originais e o radar de doze continua apenas observação.
