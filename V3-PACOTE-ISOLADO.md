# Pacote V3 isolado — etapa 1 do pedido de dez blocos

24/10/2026. Pesquisa offline; `execution_authorized=false` e `approved=false`.
Nenhum arquivo de `spot_engine/` ou `ai_shadow/` foi modificado nesta entrega.
A sessão multipar existente, seu prazo, carteira e identidade permanecem separados.

## Diferenças resolvidas explicitamente

- O texto novo define **três hipóteses de entrada e um filtro de observação**.
  Não são as quatro estratégias da ESPECIFICACAO-V3.md: divergência confirmada
  e VWAP reversion continuam no pesquisador anterior. O novo pacote é uma
  variante nomeada `observation-1`, sem substituir o estudo anterior.
- RR bruto ponderado = `(0.40*2 + 0.35*3.5 + 0.25*5)/1.8`
  = **1,81944R**, antes de custos e arredondamento. O numerador é 3,275 ATR,
  não 2,6R. O planejador exige RR líquido mínimo de 1,5.
- Reversão em regime RANGE exige preço abaixo do VWAP. Exigir simultaneamente
  preço acima do VWAP/ribbon e no terço superior da banda tornaria as regras
  contraditórias. Nessa variante, contexto e bandas têm alinhamento específico
  para RANGE; essa adaptação é uma hipótese nova, ainda sem validação econômica.
- Score tem cinco blocos binários de 20 pontos. Na prática, corte 70 exige
  pelo menos 80; nunca se converte score em confiança calibrada de IA.
- 620 candles 15m cobrem apenas 6,46 dias. A política existente usa aquecimento
  3n: 600 candles completos 4H e 150 diários. O pacote agrega 15m causalmente,
  ignora o primeiro bucket superior incompleto e permanece UNKNOWN até pronto.
  Não usa os últimos candles superiores como se fossem conhecidos no passado.
- `TransitionFilter` só observa; UNKNOWN/CRISIS sempre bloqueiam candidatos.
- Os 5 USDT são teto de custo por proposta, incluindo taxa. Três parcelas
  podem ficar inexequíveis; recusa-se o plano sem elevar risco ou capital.
- Classificar três regimes em replay demonstra cobertura de regras, não
  acerto de classificação. Replay não cumpre 48h de forward test e não
  substitui revisão humana de dez sinais.

## Arquivos e contrato

| Arquivo | Responsabilidade |
|---|---|
| `v3_engine/context.py` | Adaptador incremental do pesquisador causal já testado, snapshots independentes e agregação UTC |
| `v3_engine/regime.py` | Prioridade UNKNOWN, CRISIS, BREAKOUT, TREND, RANGE, TRANSITION |
| `v3_engine/scorer.py` | Cinco componentes auditáveis; score não é probabilidade |
| `v3_engine/strategies.py` | Classes evaluate(state), ENTER/HOLD/OBSERVE de pesquisa, sem broker |
| `v3_engine/risk_v3.py` | Proposta Decimal precisão 80, teto 5 USDT e validação das três parcelas |
| `v3_engine/engine_v3.py` | Replay CSV com manifesto, hash de dependências, STOP e relatório separado |
| `tests/test_v3_engine.py` | Causalidade, regimes, score, VWAP, STOP, filtros e isolamento |

Não há estado de posição ou EXIT inventado. Breakeven, trailing, time stop,
pausa por quatro perdas, daily/DD persistentes e execução parcial **não estão
implementados neste pacote**. O planejador recebe orçamentos restantes já
validados; não mantém carteira nem consome caixa. Os controles existentes do
motor ativo não foram substituídos por esse planejador.

## Como testar no PowerShell

```powershell
git pull
python -m unittest tests.test_v3_engine tests.test_v3_position_plan tests.test_v3_research -v
python -m v3_engine.engine_v3 --help
```

Com CSV já coletado e manifesto JSON correspondente ao lado:

```powershell
python -m v3_engine.engine_v3 --csv CAMINHO-DO-CSV --output reports/local/v3-status/replay-001.json
```

O comando nunca consulta contas, nunca conecta broker, não escreve fora de
`reports/local/v3-status/*.json`, não sobrescreve relatório anterior e verifica
STOP no diretório atual por padrão (`--stop-root` permite informar o root).
`candidate_samples` preserva até 1.000 sinais para revisão, com aviso de corte.
`signals` contém apenas os últimos 50 estados. Nenhum dos dois registra fills.

## Evidência inicial

No CSV BTC/USDT 15m já utilizado pelos estudos anteriores (70.176 candles):
55.694 barras prontas; 14.482 UNKNOWN; 40.438 TRANSITION; 4.401 RANGE;
903 BREAKOUT; 9.952 TREND. **Dois candidatos de pesquisa**, nenhum preenchimento,
nenhum PnL calculado. Não houve CRISIS nessa amostra. Os testes sintéticos
cobrem todos os seis regimes. Esta mesma amostra já foi inspecionada;
não é holdout independente. Essas contagens não validam rentabilidade.

## Matriz do pedido e trabalho restante

| Bloco | Situação após esta entrega |
|---|---|
| 1 Estratégias/motor | Contexto, regimes, score, classes e replay isolado implementados; loop REST 24h e gestão de posição pendentes |
| 2 Migração ATR do motor ativo | Não aplicada: requer migração coordenada do motor correto, reconciliação e sessão parada; `spot-runs` e carteira multipar são motores diferentes |
| 3 Walk-forward/bootstrap | Auditorias cronológicas e custos já existem, mas não implementam todo o pipeline rolling/bootstrap solicitado |
| 4 Shadow bridge | Não integrado; score/100 não será apresentado como probabilidade calibrada; contratos originais preservados |
| 5 Scanner com regime/prioridade | Não alterado; sobretudo `selection.py` participa da identidade da carteira ativa |
| 6 View V3 | Não ligada ao dashboard; estes JSONs são replay offline, não telemetria de motor ao vivo |
| 7 Integridade | Oito contratos novos, além dos testes existentes; não se sobrescreveram suítes de mesmo nome |
| 8 Contexto multi-TF | Agregação causal de 15m implementada; downloader separado 4H/daily não implementado nem necessário para este replay |
| 9 Migração de sessão | Nenhuma sessão movida; script ainda pendente. STOP nunca deve ser removido automaticamente para migrar |
| 10 Coletor paralelo | Pendente. Timeout de Future não interrompe uma requisição bloqueada; exige timeout de transporte e cliente seguro por thread |

Próxima etapa técnica: validar a máquina de estado de posição ATR/saídas em
testes offline, antes de construir um novo observador REST separado. As etapas
48h observação e dez revisões humanas continuam bloqueando qualquer paper fill
da variante nova. Não há ativação live ou promoção automática por métricas.
