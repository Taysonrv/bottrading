# Ampliação do radar para 12 pares

Universo de observação: BTC, ETH, SOL, BNB, XRP, DOGE, ADA, LINK, AVAX, LTC, DOT e NEAR, todos contra USDT. Disponibilidade depende da resposta pública Spot; erro de um par é registrado, não substituído por sucesso antigo.

O radar usa a mesma regra EMA/ATR 15m, sem afrouxar filtros ou forçar sinais. Conta intenção de entrada uma vez por par e candle fechado. Não transforma esse contador em ordens, fills ou lucro. A primeira leitura inclui o último candle fechado, sem supor execução retroativa.

```powershell
python -m expanded_radar
python -m expanded_radar --watch
```

A segunda opção observa por até 24h, com leituras a cada aproximadamente 60s após o término da varredura, respeitando STOP global/local. `reports/local/expanded-radar/latest.json` guarda sinais e contadores; `health.json` indica a saúde da última tentativa. Considere também a idade dos dois arquivos: interrupção do processo não atualiza os registros. Não é um serviço permanente com renovação automática.

O motor PAPER de seis pares em andamento não é modificado. Seu ledger só aceita os seis pares originais. A expansão da execução requer uma nova versão identificada e uma sessão separada depois de preservar o resultado e conferir inventário; não se altera o universo em uma carteira ativa por troca de constantes. Isso evita invalidar identidade e reconciliação do banco.

Mais pares podem ampliar oportunidades; não garantem mais fills nem retorno. Com 20 USDT, mantemos uma posição e orçamento até 6 USDT, risco estimado até 1%, perda diária 3% e drawdown 10%. Aumentar posições simultâneas ou reduzir alvos para gerar volume pode inviabilizar os mínimos ou tornar os custos dominantes. Não fazer isso sem um novo experimento.
