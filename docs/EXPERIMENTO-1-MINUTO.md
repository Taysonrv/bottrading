# Piloto de rompimento em 1 minuto

Módulo isolado: `spot_engine.minute_research`. Não modifica a configuração,
carteira ou código da sessão EMA ativa. Não conecta conta nem envia ordens.

Regras fixadas antes da primeira execução:

- Universo: BTC, ETH, SOL, BNB, XRP e DOGE contra USDT.
- Tendência: EMA20 > EMA50 nos candles completos de 15 minutos e fechamento
  atual acima da EMA50. Aquecimento de 150 candles de 15 minutos.
- Gatilho: fechamento de 1 minuto acima das máximas dos 20 candles anteriores;
  volume de pelo menos 1,5 vezes a média dos 20 candles anteriores.
- Entrada simulada na abertura seguinte, com slippage adverso.
- Distância de stop: maior entre 1,5 ATR14 e 0,3%; recusa acima de 2%.
- Alvo bruto: duas vezes a distância do stop. Recusa quando o alvo não cobre
  as taxas e slippage estimados da ida e volta.
- Stop primeiro quando ambos os níveis são tocados no mesmo candle; gaps
  podem produzir saída abaixo do stop.
- Capital independente de 20 USDT por janela, teto de entrada 6 USDT incluindo
  taxa, risco estimado de até 1%, perda diária de 3% e drawdown de 10% observados
  em aberturas/fechamentos. Uma posição por teste. Não é carteira compartilhada.
- Quantidade arredondada para o lote atual; mínimos atuais verificados também
  no stop estimado. Saída abaixo do mínimo permanece marcada, sem inventar fill.

Quatro semanas independentes de avaliação, precedidas de aquecimento, são um
piloto operacional. Não substituem dois anos de histórico e teste prospectivo.
Os dados de todos os pares têm o mesmo início e fim UTC, fixados antes da coleta.
Os candles em formação são excluídos. Não se faz otimização após ver resultados.

Custos base assumidos: 0,1% de taxa por lado e 0,1% de slippage por lado.
No stress ambos dobram; a mesma regra de viabilidade pode recusar mais entradas.
Uma janela sem operações deve ser interpretada como ausência de evidência.

Não reproduz spread histórico, precisão de preço/tick, fila, ordens parciais,
latência medida ou indisponibilidade da API em cada instante. Filtros são atuais,
não históricos. O resultado pode superestimar a execução real. Os arquivos
privados incluem candles, hashes do modelo/dados, regras, resultados por janela
e índice da execução; nenhuma aprovação automática é gerada.

Comandos manuais na pasta de desenvolvimento:

```powershell
.\.venv-spot\Scripts\python.exe -m unittest tests.test_spot_minute_research -v
.\.venv-spot\Scripts\python.exe -u -m spot_engine.minute_research
```

O painel Estratégias mostra os relatórios de `reports/local/spot-minute`.
Cada execução cria uma pasta nova. Este módulo não mantém um bot de 1 minuto
ligado: é uma pesquisa histórica com compras e vendas fictícias.
