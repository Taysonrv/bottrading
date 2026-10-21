# Recuo em1h com tendência4h

Pesquisa isolada em `spot_engine.pullback_research`, sem alterar a carteira ativa.
Usa os históricos15m de dois anos já coletados, com hash/manifesto verificados,
agregados em horas UTC completas. O histórico já foi examinado em outras
pesquisas; não é uma amostra nova independente.

Regras fixadas antes da execução:

- Universo BTC, ETH, SOL, BNB, XRP e DOGE contra USDT.
- Tendência: fechamento1h acima da EMA200 do último candle4h completo.
- Setup: candle1h anterior tocou a EMA20 de1h (mínima <= EMA20 <= máxima).
- Confirmação: candle1h atual fecha acima da máxima do anterior.
- Entrada simulada na abertura seguinte, com slippage adverso.
- Stop: maior entre1,5 ATR14 de1h e0,3%; recusa se exceder3%.
- Alvo bruto: duas vezes a distância do stop; recusa se não cobrir custo estimado.
- 600 candles4h de aquecimento antes de avaliar entradas. Apenas4h completos
  atualizam a EMA200, sem conhecer fechamentos futuros.
- Quatro janelas independentes,20USDT fictícios por janela e até6USDT por compra
  incluindo taxa. Uma posição por experimento, risco estimado1%, perda diária3%
  e drawdown10% em aberturas/fechamentos. Não compor os retornos das janelas.
- Custos base por lado: taxa0,1% e slippage0,1%. Cenário de stress dobra ambos.
- Lotes/mínimos atuais, inclusive no stop estimado. Não aumenta compra para
  atender mínimo. Saída inviável permanece marcada, sem inventar preenchimento.

Não reproduz precisão histórica de preço, spread, fila, latência, ordens parciais
ou proteção intrabar contínua. Stop é sintético e gaps podem exceder a perda
estimada. Dados e filtros não demonstram execução real. Nenhuma aprovação
automática é gerada. Comparações múltiplas podem produzir ganhos por acaso.

Executar manualmente na pasta do projeto:

```powershell
.\.venv-spot\Scripts\python.exe -m unittest tests.test_spot_pullback -v
.\.venv-spot\Scripts\python.exe -u -m spot_engine.pullback_research --data-dir CAMINHO_DOS_CSVS_15M
```

São exigidos exatamente seis CSVs (um por par) com a mesma janela. Relatórios
privados em `reports/local/spot-pullback`, visíveis na aba Estratégias.
O comando executa testes históricos e termina; não ativa trading prospectivo.
