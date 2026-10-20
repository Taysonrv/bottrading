# Motor Spot modular — entrega incremental

## Premissas iniciais

Python 3.11+, PC Windows atual; componentes independentes do sistema operacional para posterior VPS Linux. Capital de simulação 20 USDT, BTC/USDT configurável, 1h, perfil conservador, uma posição, teto de 5 USDT por ordem. Escolha inicial única: EMA 20/50 com tendência EMA 200 e ATR. Os parâmetros são hipóteses para testar, não resultados de otimização.

O pacote novo não é iniciado por `iniciar.py` e não altera a identidade ou os limites da sessão atual. O limite de drawdown de 10% pertence ao motor novo; a sessão existente mantém 15%. Migrar exigirá encerrar e preservar a sessão anterior. Não substituímos os módulos homônimos existentes na raiz.

## Estrutura e sequência

```text
spot_engine/
  __init__.py
  config.py       # entregue: parâmetros imutáveis e validação local
  data.py         # entregue: ccxt REST e observação WebSocket de candles fechados
  strategy.py     # entregue: classe incremental de sinais EMA/ATR, sem ordens
  risk.py         # entregue: propostas e travas persistentes; execução pendente
  execution.py    # adaptadores paper/testnet; reconciliação e IDs idempotentes
  backtest.py     # mesmas regras, decisão no fechamento/execução posterior
  logger.py       # SQLite transacional, exportação CSV e UTC
  main.py         # composição; live indisponível até implementação e validação
 tests/test_spot_config.py
```

Módulos sem a marca entregue ainda estão pendentes. O coletor usa ccxt e websockets; pandas e numpy ficam para a estratégia e o backtest. O ambiente isolado de integração desta entrega usa Python 3.12, ccxt 4.5.89 e websockets 17.3. Instalação no Python 3.15 do operador ainda não foi verificada; os testes sem dependências também rodam no Python 3.15.

## Módulo 1: configuração

`spot_engine/config.py` usa apenas biblioteca padrão, Decimal para valores monetários/frações e dataclass congelada. Lê variáveis `TRADING_*`, valida também construção direta, recusa NaN/Infinity, live, derivativos, stop desabilitado e limites superiores ao solicitado. Não conecta à exchange, não carrega chaves nem lê `.env` automaticamente. Use variáveis do terminal; um eventual `.env` será local, ignorado pelo Git, sem segredos em exemplos.

Padrões: risco/operação 0,01; perda diária 0,03; drawdown 0,10; stop 0,02; alvo 0,04; EMA 20/50/200; ATR 14 com faixa ATR/preço 0,001–0,05; taxa 0,001 por lado, slippage 0,001 por lado e latência hipotética 500 ms; histórico 2 anos e Testnet 28 dias. Frações não são percentuais inteiros. Configurar um limite não significa que o motor já o aplica: a aplicação será responsabilidade de risk/execution, ainda pendentes.

Teste e inspeção local:

```powershell
python -m unittest tests.test_spot_config -v
python -m spot_engine.config
$env:TRADING_SYMBOL = "ETH/USDT"
$env:TRADING_TIMEFRAME = "15m"
python -m spot_engine.config
```

## Critérios dos próximos módulos

- Dados: UTC, somente candles fechados, remoção de duplicados, detecção de lacunas, no mínimo dois anos disponíveis do par. Não inventar trechos ausentes ou assumir que dois anos representam todos os regimes.
- Estratégia: cruzamento confirmado após warm-up suficiente da EMA 200; parâmetros e regras de ATR congelados antes do teste reservado; sem usar máxima/mínima futura.
- Risco: orçamento máximo de 1% inclui custos estimados e distância até stop; não equivale a limite garantido da perda. Limites diários usam patrimônio marcado e dia UTC; persistir base diária, pico e travas em reinícios. STOP verificado antes de toda ordem. Definir proteção de posições abertas mesmo quando novas entradas estiverem bloqueadas.
- Execução: consultar filtros atuais por par (PRICE_FILTER, LOT_SIZE, MARKET_LOT_SIZE, MIN_NOTIONAL/NOTIONAL quando aplicáveis), saldo livre, precisão e permissões. Timeout de envio exige reconciliar clientOrderId antes de repetir; nunca repetir uma compra às cegas. Preenchimentos parciais atualizam inventário e proteção de quantidade efetivamente executada.
- Validação: walk-forward cronológico, warm-up causal por janela, conjunto final reservado, registro de todas as variantes e cenários de custos; retorno líquido, taxa de acerto, profit factor, Sharpe com frequência explícita, DD e buy & hold alinhado, sem inventar métricas indefinidas.
- Testnet: 2–4 semanas para integração, falhas, proteção e reconciliação; acompanhar resets. Não comprova vantagem econômica. Só depois avaliar liberação separada do adaptador live com capital mínimo, chave Spot sem saque e IP restrito.
- Notificações: abertura, fechamento, falha e trava, desacopladas da execução; falha no Telegram não remove proteção. Nunca registrar chaves, URLs com credenciais ou respostas sensíveis.

## Limitações importantes

0,1% é hipótese inicial de taxa por lado, não confirmação da comissão da sua conta/par. Os custos devem ser consultados ou informados antes de qualquer execução. Slippage e latência não ficam realistas apenas por adicionar constantes: cenários de estresse, spread, lacunas e regra explícita de preenchimento são necessários.

Com 20 USDT, 1% equivale a 0,20 USDT de risco teórico. O mínimo de ordem pode impedir uma entrada compatível com esse orçamento; nesse caso o bot deve recusar, sem aumentar o risco para forçar compra. Stop pode executar pior que o preço de disparo, e stop-limit pode não preencher. Backtest positivo, múltiplas estratégias ou taxa de acerto alta não garantem lucro.

## Fontes primárias consultadas em 20/10/2026

- Filtros: https://github.com/binance/binance-spot-api-docs/blob/master/filters.md
- Spot Testnet e resets: https://github.com/binance/binance-spot-api-docs/blob/master/testnet/general-info.md


## Módulo 2: dados públicos — entregue

Código completo em `spot_engine/data.py`; dependências fixadas em `requirements-spot-data.txt`. Sem chaves: o adaptador ccxt expõe somente horário e OHLCV públicos, com Spot, rate limiter e timeout de 15 segundos. Não é iniciado pelo painel/iniciador atual.

- Janela UTC `[início,fim)`, alinhada; nenhum candle com fechamento posterior ao horário público da Binance é aceito no histórico.
- Paginação explícita por `since`, inclusive quando uma página tem menos de 1.000 itens. Sobreposições iguais são deduplicadas; divergências, falta de progresso, OHLC inválido e intervalos ausentes abortam.
- Até três tentativas por consulta em falhas transitórias de rede, com esperas de 1 e 2 segundos. Rate limit/ban interrompe; não executa ciclo agressivo de reconexão REST.
- Arquivos únicos CSV e manifesto JSON em `reports/local/spot-data/`, ignorados pelo Git. SHA-256 verifica integridade dos bytes do CSV; não é assinatura da Binance nem validação financeira. Falha durante gravação pode deixar CSV sem manifesto: não use esse arquivo como conjunto aprovado.
- WebSocket público usa `k.x == true`, par/timeframe corretos, evento não futuro e defasagem máxima de 120 segundos. Exige relógio local sincronizado. Observação limitada a 1–3.600 segundos, com até três reconexões. Duplicata idêntica é ignorada; conflito/retrocesso/lacuna interrompem. `ClosedSequence(previous=último_candle)` permite verificar continuidade em relação ao histórico REST.
- A recuperação automática de lacunas via REST e a persistência contínua do streaming serão ligadas na orquestração futura; não há recuperação silenciosa ou geração de sinais nesta entrega. Não confunda este teste limitado com serviço 24/7.

### Como instalar e testar

Use ambiente virtual separado para não alterar dependências do bot existente. Python 3.12 foi verificado com as dependências; Python 3.11+ é o alvo, mas cada combinação precisa de teste.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-spot-data.txt
.\.venv\Scripts\python.exe -m unittest tests.test_spot_config tests.test_spot_data -v
.\.venv\Scripts\python.exe -m spot_engine.data --years 2
.\.venv\Scripts\python.exe -m spot_engine.data --stream-seconds 30
```

O download usa `TRADING_SYMBOL`/`TRADING_TIMEFRAME` da configuração. Não altera carteira, relatórios de sessão, STOP ou identidade da estratégia. Zero candles fechados em trinta segundos é esperado em muitos intervalos de 15m/1h/4h. Não diminuímos o timeframe para forçar eventos.

### Evidência de integração em 20/10/2026

Coleta pública real BTC/USDT 1h: 17.520 candles, 18 páginas, dois anos completos, sem lacunas, manifesto local com hash. Observação WebSocket de dez segundos concluída sem candle fechado. Isso testa transporte e integridade; nenhum sinal, lucro ou backtest foi calculado. Os dados continuam privados e não são enviados ao repositório.

A série OHLCV não informa ordem intrabar entre máxima e mínima, fila de execução, spread ou momento exato em que um candle histórico ficou disponível. O futuro backtest precisará tratar essas limitações e executar sinais em instante posterior. Não usar valores da vela em formação.

Fontes: https://docs.ccxt.com/docs/manual e https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md (consultadas em 20/10/2026).


## Correcao de instalacao no Windows/Python 3.15

A instalacao do operador falhou em cffi 2.0.0 no Python 3.15: pip tentou compilar e exigiu Visual C++ Build Tools. Os testes com adaptadores falsos passaram, mas isso nao confirma a instalacao do ccxt nem o download real.

Use o instalador abaixo. Ele procura Python 3.12 pelo launcher `py` e, se ausente, pelo runtime local do Codex. Cria `.venv-spot` separada, sem apagar a `.venv` existente ou mudar o Python padrao. Instala somente wheels binarias; interrompe ao primeiro erro. Se nao encontrar Python 3.12, pede sua instalacao, sem baixar outro interpretador automaticamente.

```powershell
git pull
.\configurar-spot.ps1 -BaixarHistorico
```

A opcao `-BaixarHistorico` executa a coleta publica somente depois da instalacao, `pip check` e 57 testes. Sem a opcao, prepara apenas o ambiente. Nao modifica saldo, STOP ou estrategia. Uma pasta `.venv-spot` incompleta ou com outra versao e preservada para revisao, sem remocao automatica. Nas proximas coletas use `.\.venv-spot\Scripts\python.exe`, pois `python` pode continuar apontando para 3.15.


## Módulo 3: sinais EMA/ATR — entregue

Código completo: `spot_engine/strategy.py`; testes: `tests/test_spot_strategy.py`. A classe `EmaAtrStrategy` recebe configuração validada e um candle fechado por chamada, com instante de decisão explícito. Não lê saldo nem envia ordens. O módulo atual usa cálculo incremental com biblioteca padrão; pandas/numpy ficam para análise vetorial e relatórios do backtest, sem acrescentar dependências ao caminho de sinais agora.

### Regras congeladas desta versão

- EMA recursiva iniciada no primeiro fechamento: alpha = 2/(período+1), equivalente a `ewm(adjust=False)` sem valores ausentes. Padrões 20/50/200.
- ATR de Wilder: true range é o maior entre máxima-mínima, distância da máxima ao fechamento anterior e distância da mínima ao fechamento anterior. Na primeira barra usa máxima-mínima. Inicialização pela média dos primeiros 14 TR; depois suavização com alpha = 1/14.
- Aquecimento mínimo: três vezes o período da EMA de tendência (600 barras no padrão), ou ATR+1, o que for maior. Isso reduz dependência da semente, sem eliminá-la por completo.
- `ENTER_LONG`: EMA rápida anterior <= lenta anterior e rápida atual > lenta atual, fechamento > EMA 200, ATR/fechamento entre 0,001 e 0,05 inclusive. Comparações usam indicadores apenas até o candle corrente fechado.
- `EXIT_LONG`: cruzamento inverso da EMA rápida para baixo da lenta. Não é bloqueado pelo filtro ATR de entrada. O futuro motor deve ignorar essa intenção se não houver posição; não é autorização para short.
- Demais casos: `HOLD`, com motivos `WARMUP`, `NO_CROSS`, `TREND_FILTER` ou `ATR_FILTER`. Sem compra repetida simplesmente por permanecer acima das médias.
- Duplicatas, retrocesso do relógio, candles em formação, lacunas e overflow são recusados sem alterar o estado dos indicadores. Continuidade será recuperada pelo módulo de dados; nunca pulada silenciosamente.

A classe mantém os indicadores somente em memória. Reinício exige reproduzir o histórico causal; checkpoint/recuperação serão responsabilidade da orquestração futura. Não injete a classe diretamente na sessão antiga.

### Como testar e inspecionar

```powershell
git pull
.\.venv-spot\Scripts\python.exe -m unittest tests.test_spot_strategy -v
$csv = Get-ChildItem .\reports\local\spot-data\BTC-USDT-1h-*.csv | Sort-Object LastWriteTime | Select-Object -Last 1
.\.venv-spot\Scripts\python.exe -m spot_engine.strategy --csv $csv.FullName
```

Use um CSV do par/timeframe configurado; a falta de arquivo ou divergência de configuração deve ser corrigida antes de executar. O leitor também confere a grade temporal, colunas UTC, cobertura e hash do manifesto. Hash detecta mudanças em relação ao manifesto; não autentica um arquivo de origem desconhecida.

A inspeção salva um resumo único em `reports/local/spot-signals/` com contagem de intenções, configuração e hashes do CSV/código. `orders=0`, `pnl=null`, `approved=false`. Intenções de entrada/saída não são execuções, ciclos completos, taxa de acerto ou lucro. A data de decisão histórica é o fechamento teórico, não uma medição de latência real.

Esse relatório é exploração de histórico. Não escolher parâmetros após observar os resultados e chamar o mesmo período de teste reservado. O backtest futuro deverá separar períodos, custos, instantes executáveis e tratamento intrabar. Stop, take profit, dimensionamento e limites de 1%/3%/10% continuam pendentes do próximo módulo `risk.py`.

Limitações: cruzamentos podem perder em mercados laterais, EMA atrasa, ATR não prevê direção e gaps podem ultrapassar stops. Testes causais não demonstram vantagem financeira.

Fontes primárias consultadas em 20/10/2026: https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.ewm.html e https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/atr.


## Módulo 4: risco persistente e dimensionamento — entregue

Código: `spot_engine/risk.py`; testes: `tests/test_spot_risk.py`. Módulo independente, sem rede, sem ordens e sem mudança na sessão antiga. Não é chamado pelo iniciador atual. Usa Decimal com precisão local fixa e SQLite transacional (synchronous FULL) para serializar as atualizações de risco.

`Account` exige patrimônio marcado e caixa livre não negativos e coerentes, posições abertas e entradas pendentes. O módulo suporta uma posição por vez; recusa configuração de mais posições até existir controle de risco agregado e reservas.

`RiskManager.initialize` é explícito e exige capital configurado integralmente em caixa, sem exposição. O estado fica em `reports/local/spot-risk/`, privado e ignorado pelo Git. Nunca inicializa automaticamente quando perde checkpoint ou marcador. Mudança de configuração, sessão ou bytes de risk.py causa incompatibilidade e exige revisão; não apague estado para contornar travas. Não há garantia contra adulteração deliberada ou remoção de todos os arquivos por um administrador.

### Limites e persistência

- Risco teórico de stop limitado a 1% do patrimônio marcado, incluindo taxas estimadas de entrada/saída e slippage. Com 20 USDT, teto teórico de 0,20 USDT, podendo ser menor pelo orçamento restante diário/drawdown.
- Perda diária de 3% usa base marcada da primeira observação do dia UTC (capital na inicialização). Trava persiste após recuperação e reinício; só a mudança de dia UTC libera a trava diária. Perdas intradiárias entre observações não são reconstruídas automaticamente.
- Drawdown de 10% usa pico global de patrimônio marcado. Ao atingir, trava permanece em outro dia ou após recuperação, até revisão externa; não há função automática de reset.
- Limites de perda bloqueiam novas entradas, mas permitem proposta de redução de inventário. STOP manual tem prioridade e bloqueia entrada e redução: não liquida automaticamente. Falha na verificação de STOP recusa a avaliação.
- Transições DAILY_LOSS, DRAWDOWN e STOP são registradas no SQLite uma vez por ativação. Não são notificações Telegram entregues: o futuro módulo de execução/notificações precisará encaminhá-las e confirmar envio.

### Proposta de tamanho

`plan_entry` exige cotação com no máximo 5 segundos, filtros normalizados com no máximo uma hora e par correspondente. Estima entrada adversa, stop e alvo por percentuais configurados, ajusta preços ao tick e quantidade para baixo ao step. Teto de 5 USDT por ordem inclui taxa de entrada. Considera caixa, risco restante diário/global, máximo de lote/notional e mínimos; nunca aumenta tamanho para atingir mínimo.

`Rules` representa restrições normalizadas de LIMIT (lote/preço/notional), não todos os filtros da Binance. Ainda faltam consulta e tradução de exchangeInfo, filtros dinâmicos de preço, regras específicas de MARKET, média de referência para notional de mercado e reconciliação do saldo real. Por isso toda proposta tem `execution_authorized=False`; não encaminhá-la diretamente a uma exchange.

`assess_reduction` exige quantidade positiva <= inventário informado e posição existente. Saídas também precisarão validar lote, notional, saldo, cotação e posição protegida no adaptador de execução. A função não vende nem instala stop.

Propostas não reservam saldo ou risco e não são autorização durável. Antes de cada envio o próximo módulo deve reconciliar conta/pendências, reservar de forma atômica, reavaliar STOP e limites, usar clientOrderId e proteger a quantidade efetivamente preenchida. SQLite serializa checkpoints locais, sem atomicidade com a exchange. Stops não garantem preço de saída nem limite máximo da perda, especialmente em gaps e falta de liquidez.

### Como testar

```powershell
git pull
.\.venv-spot\Scripts\python.exe -m unittest tests.test_spot_risk -v
```

Os testes usam apenas carteiras e filtros fictícios em diretórios temporários. Cobrem custos, orçamento restante, mínimo inviável, preços/tamanhos, trava diária, pico e drawdown, reinício, corrupção, relógio, STOP, saídas de redução e entradas pendentes. Não inicializam risco para sua carteira atual. Nenhuma nova dependência.

Fonte de filtros: https://github.com/binance/binance-spot-api-docs/blob/master/filters.md (consultada em 20/10/2026). Próxima entrega: execução paper com reconciliação, reservas, preenchimentos e proteção; execução real permanece indisponível.
