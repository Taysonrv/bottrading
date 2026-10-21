# Integração operacional — revisão de 21/10/2026

## Situação verificada
Os relatórios da execução e do radar estavam sem atualização há aproximadamente 13 horas. O texto RUNNING salvo no disco não confirma um processo ativo. Não foi demonstrada vantagem lucrativa nas validações realizadas.

| Tela/componente | Função | Envia ordens? |
| --- | --- | --- |
| Terminal / EMA | Carteira de 20 USDT fictícios, decisões, ordens, preenchimentos e risco da sessão ema20 | Apenas simuladas BTC/USDT, 1h |
| Radar | BTC, ETH, SOL, BNB, XRP e DOGE em 15m | Não |
| Estratégias / pesquisa | Comparações históricas e custos | Não |
| Kronos | Cenários experimentais e avaliação de previsão | Não |
| MetaMask | Consulta de carteira e laboratório de custos | Não; nenhuma assinatura |
| Simulação antiga / relatórios antigos | Experimentos anteriores com identidade e carteira próprias | Não integram o saldo EMA |

Não somar carteiras dos experimentos. CoinGecko fornece contexto; preços de execução vêm dos dados públicos da Binance. Notificações antigas não representam cobertura de alertas do motor EMA.

## Novo ponto de entrada
`operar.py` supervisiona motor EMA, radar e painel no mesmo terminal. O painel recebe um estado central com idade dos dados e escopo de cada componente. Se um filho terminar, o supervisor encerra os demais; não reinicia carteiras ou remove travas. Os logs ficam em reports/local/system-*.log.

No terminal do VS Code, na pasta do repositório atualizado:

```powershell
git pull --ff-only
.\.venv-spot\Scripts\python.exe operar.py
.\.venv-spot\Scripts\python.exe operar.py --start
```

O primeiro comando Python apenas verifica. O segundo inicia a operação PAPER. Use o endereço e código impressos nesse terminal. Encerre os iniciadores antigos antes; porta ocupada ou trava existente bloqueiam a inicialização. Pode selecionar outra porta com --port 8769.

Ctrl+C pede ao motor que cancele pendências e preserve a carteira, acionando STOP local. STOP não liquida posições. A trava fica para revisão. A sessão existente mantém seu prazo original: --hours 24 não renova uma sessão já criada. Sessões vencidas precisam de revisão e continuidade explícita, sem apagar o histórico.

## Fluxo conectado
Dados públicos → candles fechados → estratégia EMA → risco determinístico → corretora simulada → diário SQLite → painel.

Radar multipar → observação/seleção experimental → painel. Ainda não há ligação do radar ao executor com carteira compartilhada.

## O que falta para operação contínua completa
1. Carteira multipar única com reservas transacionais, alocação e limites globais; não criar 20 USDT fictícios independentes para cada moeda.
2. Continuidade de sessões sem renovar saldo, prazo ou risco silenciosamente; recuperação de falhas e reconciliação após reinício.
3. Alertas Telegram do motor atual, incluindo interrupção, dados vencidos e proteção acionada.
4. Serviço em PC sem suspensão ou VPS, monitor externo e testes de queda de rede, reinício e falta de disco. O iniciador atual depende do terminal e computador ligados.
5. Evidência fora da amostra, custos e teste prolongado. Testnet e execução real seguem pendentes; nenhuma integração nova autoriza dinheiro real.

Os stops atuais dependem do processo em execução. A supervisão encerra em falhas, mas não garante proteção de uma posição durante indisponibilidade. A nova integração é uma etapa verificável; ainda não equivale a um bot multipar autônomo de produção 24/7.
