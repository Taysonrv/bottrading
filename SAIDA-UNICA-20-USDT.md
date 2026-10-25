# Teste: uma saída, 20 USDT fictícios

25/10/2026. Resultado: **REPROVADO**. Nenhuma alteração no motor ativo.

## Hipótese fixada antes de consultar o resultado

BTC/USDT em candles fechados de 1h, agregados em UTC a partir de quatro candles
15m completos. EMA20 cruza acima de EMA50, com preço acima da EMA200. Filtro
ATR14 de 0,1% a 5%, herdado da definição EMA já existente. Aquecimento 600 horas.
Uma posição long ou caixa; sem short, alavancagem, DCA ou reinvestimento externo.

- Capital inicial 20 USDT, orçamento máximo por entrada 6 USDT (30% do inicial).
- Risco estimado máximo 1% do equity por operação, incluindo taxas e slippage.
- Stop 2%, alvo 5%; saída integral após 48 candles de 1h se ainda aberta.
- Sem saída por inversão EMA, para testar a hipótese de reduzir giro por
  cruzamentos contrários. Sem parciais ou trailing.
- Perda diária 3% pausa entradas até próximo dia UTC; DD 10% fica latched.
- Cenário base: taxa 0,1% e slippage 0,1% por lado. Stress: ambos dobrados.
- Entrada apenas no próximo open, usando sinal do candle anterior fechado.
  Stop vence em ambiguidade intrabar; gap pode executar pior que o stop.

6 USDT é um orçamento de **pesquisa**, escolhido para deixar margem sobre o
mínimo normalizado 5 USDT na compra e proteção. Não é uma alteração do teto 5 da
V3 nem uma autorização para aumentar risco. Quantidade sempre arredondada para
baixo; entrada, saída de proteção e alvo passam por tick, lote e notional.
Ordem abaixo do mínimo é rejeitada, sem arredondar para cima ou somar capital.

## Resultado da amostra BTC previamente coletada

| Métrica | Custos base | Custos dobrados |
|---|---:|---:|
| Saldo inicial fictício | 20,00 | 20,00 |
| Patrimônio final fictício | 18,1204 | 18,0856 |
| Retorno líquido | −9,40% | −9,57% |
| Ciclos completos | 55 | 41 |
| Win rate | 32,73% | 31,71% |
| Profit factor líquido | 0,51 | 0,45 |
| Drawdown máximo observado | 9,66% | 9,57% |
| Taxas totais USDT | 0,6214 | 0,9199 |

Quatro blocos cronológicos, cada um com 20 USDT iniciais e aquecimento anterior:

| Bloco | Base | Stress |
|---|---:|---:|
| 1 | −2,03% | −4,61% |
| 2 | −5,64% | −8,37% |
| 3 | −0,98% | −2,55% |
| 4 | −7,03% | −9,08% |

Nenhum bloco positivo. Não somar ou compor os quatro retornos: são experimentos
separados. No contínuo base, 25 ciclos terminaram no stop, 26 no limite de tempo
e 4 no alvo. Dos 97 sinais avaliados enquanto flat, 42 reprovaram filtros de
lote/mínimo/proteção. Não buscamos outros parâmetros após ver essas perdas.

## Interpretação

Esta saída única resolve parte da inviabilidade das três parcelas e permite
gerar operações no modelo, mas **não demonstrou vantagem depois dos custos**.
Profit factor abaixo de 1 significa perdas agregadas maiores que ganhos.
Superar pontualmente comprar e manter em uma amostra negativa não transforma
uma estratégia perdedora em aprovação. Gerar ordens por si só não é o objetivo.

## Limitações

O CSV de 731 dias já foi examinado em pesquisas anteriores: não é holdout novo.
Os blocos são separação temporal exploratória de regra fixa, não treino de
parâmetros ou validação independente. O aquecimento não produz fills.

Filtros públicos consultados agora são mantidos constantes no passado, como
hipótese contrafactual: não afirmamos conhecer os filtros históricos. Não há
reconstrução de spread, fila, profundidade, latência ou preenchimentos parciais.
As saídas a mercado do modelo diferem das LIMITs sintéticas do bot ativo.

Se um gap torna a saída inferior ao mínimo, a posição fica aberta no modelo;
o relatório registra tentativas bloqueadas, sem inventar venda ou lucro.
Daily/DD observam opens e closes, não equity intrabar contínuo; não são garantia
de perda máxima. A relação de risco/retorno líquido é estimativa, não promessa.

## Reprodução e integridade

```powershell
git pull
python -m unittest tests.test_single_exit_research -v
python -m single_exit_research --csv CAMINHO-DO-CSV-15M --data-dir .
```

O CSV exige seu manifesto JSON original. O comando consulta somente filtros
públicos; não lê contas ou envia ordens. Salva relatório UUID e resumo latest
em `reports/local/single-exit-research`. A viewV3 mostra uma seção **Pesquisa /
saída única**, separada de carteira e ordens reais/simuladas em andamento.

O relatório contém hashes do CSV/código, filtros normalizados, política fixa,
cenários e blocos. `approved=false` e `execution_authorized=false` sempre.
O registro público fica em `research_results/single-exit-20261025.json`.

Próxima pesquisa pode testar outra hipótese pré-fixada e com amostra nova.
Este resultado não autoriza trocar o motor por esta estratégia ou afrouxar
os limites para fazê-la operar mais.
