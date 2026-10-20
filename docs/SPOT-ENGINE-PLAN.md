# Motor Spot modular — entrega incremental

## Premissas iniciais

Python 3.11+, PC Windows atual; componentes independentes do sistema operacional para posterior VPS Linux. Capital de simulação 20 USDT, BTC/USDT configurável, 1h, perfil conservador, uma posição, teto de 5 USDT por ordem. Escolha inicial única: EMA 20/50 com tendência EMA 200 e ATR. Os parâmetros são hipóteses para testar, não resultados de otimização.

O pacote novo não é iniciado por `iniciar.py` e não altera a identidade ou os limites da sessão atual. O limite de drawdown de 10% pertence ao motor novo; a sessão existente mantém 15%. Migrar exigirá encerrar e preservar a sessão anterior. Não substituímos os módulos homônimos existentes na raiz.

## Estrutura e sequência

```text
spot_engine/
  __init__.py
  config.py       # entregue: parâmetros imutáveis e validação local
  data.py         # próximo: ccxt REST, candles fechados e paginação; WebSocket separado
  strategy.py     # classe de sinais causal, sem acesso à conta
  risk.py         # estado persistente, limites e dimensionamento com custos
  execution.py    # adaptadores paper/testnet; reconciliação e IDs idempotentes
  backtest.py     # mesmas regras, decisão no fechamento/execução posterior
  logger.py       # SQLite transacional, exportação CSV e UTC
  main.py         # composição; live indisponível até implementação e validação
 tests/test_spot_config.py
```

Arquivos listados como próximos ainda não estão implementados. ccxt, pandas e numpy serão dependências do módulo de dados/estratégia, com versões e compatibilidade verificadas nessa entrega. Não instalamos bibliotecas sem necessidade nesta etapa.

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
