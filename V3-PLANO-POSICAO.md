# Planejador de posição v3 — pesquisa somente leitura

Implementado em `spot_engine/v3_position_plan.py`. Não lê ou altera carteira, não reserva caixa, não consulta API e não envia ordens. Um plano válido continua com approved=false e execution_authorized=false. Não está conectado ao motor ativo.

## Entradas obrigatórias

Rules normalizadas para LIMIT, Budget validado com Decimal, preço ask, ATR, score inteiro, timestamp da cotação e instante de decisão. Budget deve representar a carteira reconciliada: caixa já livre de reservas, exposição incluindo compromissos existentes e risco aberto incluindo reservas. O módulo não consegue comprovar a veracidade desse snapshot.

Bloqueia STOP, mesmo símbolo já aberto/reservado, duas posições+reservas, score<70, quote futura ou com mais de2s e filtros futuros ou com mais de1h. Não há consulta automática de metadados.

## Cálculo

- Entrada arredondada para cima ao tick após slippage previsto.
- Stop em entrada−1,8ATR, arredondado para baixo; preenchimento hipotético conservador após slippage.
- Perda por unidade inclui taxa de compra e de venda e slippage previsto.
- Orçamento de risco: menor entre1% do patrimônio × score/100, saldo do teto simultâneo5%, perda diária ainda permitida e drawdown ainda permitido.
- Caixa e exposição máxima40% também limitam quantidade. Quantidade sempre arredondada para baixo ao step.
- Valida entrada e saída inteira no stop contra os filtros normalizados.
- TP1/TP2/TP3: 2/3,5/5ATR; quantidades40%/35%/restante. As primeiras parcelas são arredondadas para baixo, a última conserva o saldo exato.
- Cada parcela precisa passar nos filtros no alvo, no preenchimento previsto e no stop hipotético. Não aumentar quantidade para alcançar mínimo.
- Relação risco/retorno **ponderada líquida** deve ser >=1,5. Não é o RR individual de TP1. Considera as quantidades efetivamente arredondadas.

O risco no stop é uma estimativa e pode ser excedido por gaps. O plano não implementa trailing, breakeven, tempo de saída, execução parcial real, fila, spread, alterações de filtros ou risco intrabar. Fee/slippage padrão0,1% por lado são hipóteses, não comissão consultada numa conta.

## Exemplos inteiramente fictícios

```powershell
python -m spot_engine.v3_position_plan --example
python -m unittest tests.test_v3_position_plan -v
```

O exemplo usa SOL/USDT com ask100, ATR2, tick0,01, step0,001 e mínimo de notional5 **mockados**, não metadados atuais da Binance.

| Capital fictício do exemplo | Resultado |
|---|---|
|20 USDT|STOP_FILTER: a quantidade limitada pelo risco não passa no mínimo na saída de proteção|
|50 USDT|PARTIAL_EXIT_FILTER: entrada/saída inteira passam, parcelas não|
|1000 USDT|Plano matemático válido, sem aprovação ou execução|

Não generalizar esses resultados para todos os pares/preços e não interpretar o exemplo maior como recomendação de aporte. Na sessão de20 USDT do projeto não foram ativadas parciais ou regras v3.

## Testes e integração pendente

Os testes cobrem conservação da quantidade das parcelas, risco e exposição, score, RR líquido depois de custos, filtros antigos, STOP, duplicidade, teto de posições e saldo pequeno. Uma chamada com float em vez de Decimal é recusada.

Próximas etapas antes de qualquer integração: orçamento reconciliado e transacional com reservas; rechecagem de todos os filtros antes de cada ordem; simulador de parciais/limites com liquidez; coordenação com saídas e stop; backtest causal da carteira completa. A interface visual de demonstração não controla este módulo.
