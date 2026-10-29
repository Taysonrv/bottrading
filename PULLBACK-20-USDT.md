# Pullback BTC/1h — hipótese exploratória V1

Regras congeladas em `experiments/pullback_20_plan.json` antes da primeira execução. Hipótese: esperar recuperação da EMA20 dentro de EMA20>EMA50>EMA200 pode evitar entradas no primeiro cruzamento. Não existe vantagem demonstrada.

Entrada: após 600 candles fechados, alinhamento das três EMAs no candle anterior e atual, fechamento anterior abaixo/na EMA20 e atual acima, candle atual positivo e ATR14/preço de 0,1% a 2%. Compra hipotética apenas na abertura seguinte. Capital 20 USDT, custo de entrada até 6 USDT, uma posição, risco estimado até 1%, stop 2%, alvo 5%, saída integral em até 48 candles. Perda diária 3%, drawdown 10%; gaps podem ultrapassar o stop. Sem alavancagem ou preço médio.

## Resultado na amostra anterior

| Cenário | Ciclos | Retorno líquido | Taxas USDT |
|---|---:|---:|---:|
| Base | 41 | -9,6773% | 0,453052 |
| Taxas e slippage dobrados | 21 | -9,4563% | 0,463877 |

Os quatro blocos base perderam: -7,0973%, -5,4088%, -1,0129%, -5,1685%. **REJEITADA; ordens bloqueadas.** Custos maiores mudam a trajetória, o número de entradas e os bloqueios de risco; o resultado do stress não significa que pagar mais melhora a estratégia.

É uma hipótese adicional formulada após conhecer o fracasso da anterior. O mesmo histórico já inspecionado serve somente para exploração. Filtros de exchange constantes projetados no passado, OHLC sem fila nem liquidez, slippage assumido e risco amostrado na abertura/fechamento continuam limitações. Nenhum novo resultado constitui validação independente.

## Reprodução offline

```powershell
python -m unittest tests.test_pullback_research tests.test_single_exit_research tests.test_single_exit_audit -v
python -m pullback_research --csv CAMINHO_DO_CSV_ORIGINAL
```

Não requer chaves nem faz rede ou ordens. O hash do CSV deve coincidir com o baseline original. Resultados ficam em `reports/local/pullback-research/`, com identidade e hashes das fontes. Não modifica saldo, sessão ativa ou estratégias de produção.

O protocolo prospectivo foi documentado, mas não iniciado porque a triagem falhou. Não ajustar parâmetros repetidamente até obter lucro na mesma amostra. Antes de outra hipótese, melhorar a evidência sobre custos executáveis e formular uma justificativa econômica nova.
