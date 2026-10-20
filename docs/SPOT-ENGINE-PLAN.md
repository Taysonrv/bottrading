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
  strategy.py     # classe de sinais causal, sem acesso à conta
  risk.py         # estado persistente, limites e dimensionamento com custos
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

A opcao `-BaixarHistorico` executa a coleta publica somente depois da instalacao, `pip check` e 26 testes. Sem a opcao, prepara apenas o ambiente. Nao modifica saldo, STOP ou estrategia. Uma pasta `.venv-spot` incompleta ou com outra versao e preservada para revisao, sem remocao automatica. Nas proximas coletas use `.\.venv-spot\Scripts\python.exe`, pois `python` pode continuar apontando para 3.15.
