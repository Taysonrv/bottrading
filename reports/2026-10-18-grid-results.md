# Grid por inventário — pesquisa histórica

Simulação com sinais no fechamento e execução na abertura seguinte, não reprodução do Grid nativo da Binance.
Histórico de 365 dias já consultado: desenvolvimento, sem confirmação independente. Nenhuma adoção.

| Hipótese | Cenário | Retorno | Comprar e manter | Drawdown | Ordens | Custos USDT | Passou cenário |
|---|---|---:|---:|---:|---:|---:|---|
| grid_range_v1 | fold_1 | -4.91% | -26.56% | 5.02% | 531 | 29.42 | Não |
| grid_range_v1 | fold_2 | -2.74% | -17.88% | 5.32% | 518 | 29.13 | Não |
| grid_range_v1 | fold_3 | -2.02% | -16.28% | 5.20% | 484 | 26.74 | Não |
| grid_range_v1 | final_reused | -2.01% | 22.63% | 3.51% | 480 | 27.13 | Não |
| grid_range_v1 | continuous | -11.16% | -37.11% | 11.80% | 2013 | 106.42 | Não |
| grid_range_v1 | stress | -4.66% | 22.14% | 5.08% | 480 | 53.52 | Não |
| grid_range_v1 | existing | -1.92% | 22.63% | 3.51% | 492 | 28.55 | Não |
| grid_range_v1 | reduce_experimental | -11.16% | -37.11% | 11.80% | 2013 | 106.42 | Não |

grid_range_v1: qualificação histórica = False; episódios = {'BTCUSDT': 30, 'ETHUSDT': 35}; rupturas/proteções = {'BTCUSDT': 29, 'ETHUSDT': 35}.

| Hipótese | Cenário | Retorno | Comprar e manter | Drawdown | Ordens | Custos USDT | Passou cenário |
|---|---|---:|---:|---:|---:|---:|---|
| grid_hybrid_v1 | fold_1 | -11.12% | -26.56% | 11.14% | 711 | 45.23 | Não |
| grid_hybrid_v1 | fold_2 | -6.04% | -17.88% | 7.05% | 698 | 45.99 | Não |
| grid_hybrid_v1 | fold_3 | -5.54% | -16.28% | 5.97% | 624 | 39.92 | Não |
| grid_hybrid_v1 | final_reused | 4.27% | 22.63% | 3.84% | 752 | 55.99 | Não |
| grid_hybrid_v1 | continuous | -11.93% | -37.11% | 19.64% | 1119 | 68.13 | Não |
| grid_hybrid_v1 | stress | -1.21% | 22.14% | 6.76% | 752 | 108.92 | Não |
| grid_hybrid_v1 | existing | 4.41% | 22.63% | 3.84% | 756 | 56.67 | Não |
| grid_hybrid_v1 | reduce_experimental | -15.01% | -37.11% | 15.09% | 1125 | 68.55 | Não |

grid_hybrid_v1: qualificação histórica = False; episódios = {'BTCUSDT': 30, 'ETHUSDT': 35}; rupturas/proteções = {'BTCUSDT': 29, 'ETHUSDT': 35}.

Inclui taxas, slippage e marcação de todas as posições. Não simula fila, liquidez, fills intradiários ou spread separado do slippage.
Faixa fixa por episódio com oito degraus; filtro lateral por médias 24/168h; intervalo mínimo por degrau = quatro vezes taxa + slippage.
Ruptura detectada no fechamento encerra o episódio e solicita alvo zero, sujeito aos limites de venda. Carência de 24h antes de novo episódio.
Híbrido usa tendência somente sem episódio de grid e fora da carência; pode errar a classificação. Não usa DCA nem martingale.
STOP do simulador prevalece. Ao gatilho de 15%, o cenário normal congela ordens e mantém posições; reduce_experimental só vende gradualmente.
As mínimas horárias simultâneas são uma aproximação conservadora de risco. O gatilho não garante perda máxima de 15%.
Desenvolvimento em três janelas anteriores ao período final (25%), além de carteira contínua, custos 2x e posições iniciais de 80%.
Pesquisa usa BTC/ETH em carteira conjunta; não inclui validações individuais por ativo. Nenhum resultado altera validation.json.

Consulta UTC: 2026-10-18T22:20:16.852684+00:00
Código: `f7f2dcd9db10c49913fa6ce57e4eec8d2744a7e39dcbaa42efbeab43aeff5d0b`.
