# Código atualizado do bot — 21/10/2026

Este pacote contém o código-fonte do painel, motor Spot, observador de seis pares,
pesquisas históricas, diário auditável e testes. Não inclui credenciais, ambiente
Python, carteiras, logs, dados de mercado nem relatórios privados de execução.
Nenhuma estratégia está aprovada para dinheiro real. Modo live não disponível.

Extraia o ZIP em uma pasta nova. Não substitua arquivos da sessão em andamento:
o motor confere a identidade do código/configuração para preservar o histórico.
Os arquivos deste pacote não retomam automaticamente a carteira de outra pasta.

## Preparar no terminal PowerShell do VS Code

```powershell
.\configurar-spot.ps1
.\.venv-spot\Scripts\python.exe -m unittest tests.test_spot_config tests.test_spot_strategy tests.test_spot_risk tests.test_spot_execution tests.test_spot_selection tests.test_spot_scanner tests.test_spot_exit_audit tests.test_spot_research_view -v
node test_dashboard_frontend.cjs
```

O script prepara `.venv-spot` com Python compatível. Node é necessário para os
testes JavaScript. A configuração não inicia bot nem envia ordens.

## Nova sessão EMA de 20 USDT fictícios

Somente se quiser iniciar uma sessão separada e não houver outra cópia dela:

```powershell
.\.venv-spot\Scripts\python.exe -u -m spot_engine.main paper --session ema20 --hours 24 --order-budget 6
```

BTC/USDT, candle1h, uma posição, teto6USDT incluindo taxa. Reiniciar com o mesmo
código/configuração antes do prazo preserva o saldo e o término original;
não concede mais24h. A sessão pode permanecer em caixa sem sinal de entrada.
Não apague o estado para contornar erros de identidade ou prazo encerrado.

## Painel local

Em outro terminal, enquanto a sessão acima estiver em execução:

```powershell
.\.venv-spot\Scripts\python.exe dashboard.py --port 8768
```

Abra `http://127.0.0.1:8768/#ema`. O código de acesso é impresso no terminal.
Se essa porta já estiver ocupada, use outra porta, por exemplo8769, e abra a URL
correspondente. O painel sozinho não inicia trading. O iniciador legado
`iniciar.py` pertence à simulação anterior; não inicia este novo motor EMA.

## Observar seis pares em15minutos

Em outro terminal, somente se não houver observador desta saída ativo:

```powershell
.\.venv-spot\Scripts\python.exe -u -m spot_engine.scanner --timeframe 15m --output reports/local/multipair.json
```

Esse observador não compra nem vende. A carteira EMA permaneceBTC/1h; a prévia
multipar usa caixa hipotético e não é autorização de entrada.

## Pesquisas e diário

```powershell
.\.venv-spot\Scripts\python.exe -u -m spot_engine.universe_research
.\.venv-spot\Scripts\python.exe -u -m spot_engine.minute_research
```

São pesquisas públicas independentes que terminam após gerar os relatórios.
O teste1minuto cobre28dias, não substitui validação longa. Recuo4h/1h e auditoria
de saídas reutilizam CSVs com manifestos, conforme `docs/EXPERIMENTO-RECUO-4H-1H.md`.
Sem os relatórios privados, a aba Estratégias informa ausência de dados até
que novas pesquisas sejam executadas. Não interpreta ausência como resultado0.

O diário verifica o hash do CSV e reconcilia bruto−taxas−slippage=líquido.
Os horários intrabar são identificados pelo candle, sem alegar precisão de fill.
Stops sintéticos dependem do processo ativo; gaps, custos e mínimos podem impedir
saídas. STOP bloqueia/cancela ordens pendentes, sem liquidação automática.
