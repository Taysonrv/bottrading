# V3 — integração operacional e limites de ativação

24/10/2026. Este documento atualiza a matriz da etapa 1 em V3-PACOTE-ISOLADO.md.
**Nenhuma ordem real. A V3 permanece OBSERVE ONLY.**

## O que está conectado

- Nova view **V3 · pesquisa**, no sidebar: regimes, ADX/RSI/ATR, score,
  últimos 50 sinais com componentes expansíveis, shadow e cobertura da sessão.
- Backend `v3_view.py` lê JSON limitado a 2 MB/arquivo e até 50 julgamentos.
  Não cai para replay offline quando o observador está indisponível. Uma
  leitura sem confirmação recente fica marcada como antiga. Não há carteira
  inventada, PnL mock nem botão de execução V3.
- O frontend reutiliza `/api/status` e o polling autenticado existente de 10s.
  O radar principal também mostra regime V3 quando houver confirmação recente.
- `v3_engine.live` observa BTC, ETH, SOL e BNB. Usa Binance pública sem chaves;
  agrega 4H/diário causalmente a partir de 152 dias de 15m fechados. Após o
  bootstrap, baixa apenas novos candles; book é consultado por ciclo.
- O coletor usa até quatro workers por padrão (teto seis), cliente por thread,
  timeout HTTP e deadline de lote. Não duplica tarefas ainda bloqueadas; uma
  falha de par não apaga o erro nem se transforma em dado válido. Há backoff
  entre ciclos com falha. Future timeout não cancela threads; encerramento
  aguarda o IO com timeout de transporte.
- O scanner EMA de seis pares ganhou diagnóstico aditivo. Com somente 620
  barras, V3 permanece UNKNOWN por falta de contexto superior. Não fabricamos
  score nem promovemos esses seis pares a estratégias V3. Campos EMA antigos
  e seleção ativa continuam com o comportamento anterior.
- Priorização por regime existe em `v3_engine.selection.choose(...,
  regime_priority=True)`, somente para pesquisa. Por padrão delega à escolha
  antiga. Não alteramos selection.py da identidade da carteira em andamento.

## Shadow: diagnóstico honesto

`shadow_bridge.py` chama policy.judge existente sem editar ai_shadow/. O proxy
de score satisfaz algebricamente o contrato, mas está rotulado HEURISTIC_NOT_AI
e NOT_CALIBRATED. Quality é limitado a 3 (o schema recusa 4). Conta e fluxo não
verificados mantêm risco inelegível e toxic_flow conservador. Por isso não há
pré-aprovação de IA nem probabilidade de lucro inferida do score.

Concordância é apenas um recorte dos últimos 50 registros de política, não
acerto, calibração ou taxa acumulada da sessão. Falha do bridge retorna erro
estruturado e não afeta o observador. Sem journal de risco compartilhado,
Kelly, chave de IA ou execução. Logs locais têm IDs únicos.

## Risco e saídas implementados como pesquisa

- `risk_v3.plan_entry`: precisão Decimal 80, teto de custo 5 USDT, 25% equity,
  risco 1%/5% agregado, exposição 40%, caixa, dados frescos e filtros de todas
  as três parcelas. RR **líquido** >=1,5; caso contrário rejeita.
- `position.py`: máquina pura de candle, sem ledger. SL antes dos TPs em
  ambiguidade intrabar; gaps com preço adverso; parcelas 40/35/25; breakeven
  após PnL realizado >=0,8R inicial total; trailing após máxima >=1,5R; stop
  novo só vale no candle seguinte; time stop de 32 barras. Quantidades/custos
  proporcionais reconciliam. Saídas são hipotéticas, não reproduzem fila,
  profundidade, latência ou execução real de stop.
- `risk_state.py`: contrato puro para STOP, perdas diárias 3%, DD10% latched,
  pausa latched após quatro perdas. Daily reseta em novo dia UTC; DD e pausa
  exigem revisão. Não é um checkpoint financeiro integrado ao observador.
- `atr_protection.levels`: entry 50.000, ATR100 e stop1,8 => **49.820**.
  A regra one-exit TP2ATR/SL1,8ATR dá só1,11R bruto. Não satisfaz 1,5R líquido.

**Não migramos as proteções da carteira ativa.** Alterar portfolio.py ou
selection.py mudaria sua identidade e o comportamento em execução. O pedido
exige validação antes de novos fills; o histórico abaixo reprovou. As saídas
ATR estão implementadas isoladamente para testes, não injetadas na sessão
atual. O config.json legado não governa a carteira multipar e não foi alterado
para dar a impressão de ativação.

## Walk-forward e evidência

```powershell
python -m spot_engine.validation --pairs BTCUSDT ETHUSDT --timeframe 15m --csv-dir data
```

Requer um CSV com manifesto por par; recusa ambiguidade ou ausência. Usa
17.520 barras de contexto/treino, 5.840 OOS, passo2.920. Regras fixas: não há
otimização ou escolha do melhor parâmetro no treino. Cinco cenários de custo,
1000 reamostragens reproduzíveis de cashflows por janela, P5/P25/P50/P75/P95.
Guarda seed, hashes e configurações. Os cashflows reamostrados não são um
novo caminho executável com gestão de risco reconstruída.

No BTC15m já coletado: **17 janelas OOS, zero positivas com custos base**;
retornos de aproximadamente −5,79% a −0,21%. Zero janelas atenderam fase1.
O teste cobre a EMA/ATR existente, **não é backtest das novas classes V3**.
Esta amostra já foi estudada e as janelas sobrepõem: não é holdout independente
nem dezessete evidências independentes. Resultados não se somam/compõem.

O gate de pesquisa requer >=3 janelas com retorno positivo, >=30 trades cada,
win rate>.45, PF>1.3, DD<.15, Sharpe>.5, bootstrap P25>−.05. Todos os resultados
continuam approved=false. Um gate histórico não inicia paper nem Testnet.
Fase2: sessão separada, 30+ trades, score médio>=70 e sem halt. Fase3:
2–4 semanas Testnet separada. Há ainda a revisão humana de dez sinais.

## Comandos / operação em um terminal

```powershell
git pull
python -m unittest discover tests -v
node test_dashboard_frontend.cjs
```

Para uma inicialização futura do supervisor, após verificar que não há outra
instância rodando (não executar por cima do supervisor atual):

```powershell
python operar.py --engine portfolio --v3-observe --start
```

Painel já externo: acrescentar `--execution-only`. O observador é um componente
separado, sem reinício automático após saída, sem renovação do prazo da carteira.
Se for preciso somente observar, sem iniciar outro motor:

```powershell
python -m v3_engine.live --data-dir . --hours 48
```

STOP global e STOP de v3-runs são respeitados. Não apague STOP para fazê-lo rodar.
O observador não importa saldo nem interfere nas ordens da carteira ativa.
Cobertura conta só intervalos recentes entre ciclos saudáveis, não o replay,
o bootstrap ou lacunas >45s; reinício zera cobertura medida nesse processo.
48h no calendário não garantem48h de cobertura. O relatório nunca declara
dez revisões humanas automaticamente. Tudo permanece sem execução autorizada.

## Migração e pendências de validação

`scripts/archive_session.py` e MIGRACAO.md implementam arquivo de EMA parada
e sem posição, sob lock, com confirmação explícita e registro de movimentos.
O script não move a carteira multipar, não remove STOP nem sobrescreve sessões.

Pendente por evidência/tempo, não por falta de um botão: completar cobertura
forward, revisar dez sinais reais, backtest independente da máquina V3 e suas
parcelas com dados/filtros adequados, Testnet e aprovação de implantação.
Essas condições não serão simuladas para dizer que o pacote está validado.
