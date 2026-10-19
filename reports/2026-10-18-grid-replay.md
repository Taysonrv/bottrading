# Replay operacional do Grid

**Amostra curta de negócios públicos reais; preenchimentos e carteira simulados. Não valida rentabilidade.**

Capital fictício: 1.000 USDT. Par: BTCUSDT. Eventos: 13372. Duração: 599.835 segundos.
Período solicitado confirmado na coleta: Sim. Intervalo entre primeiro e último evento pode ser menor que a duração solicitada.
Patrimônio marcado: 1000.00000 USDT. Taxas simuladas: 0.00000 USDT.
Preenchimentos: 0. Ciclos completos compra/venda: 0.
Ordens abertas antes do encerramento: 4. Reserva antes do encerramento: 98.21822 USDT.
Ordens após cancelamento final: 0. Episódio rompido/travado: False.

Faixa e degraus definidos apenas pelo primeiro negócio, sem ajuste após consultar os resultados.
Ao romper ±3% da âncora, cancela ordens e mantém inventário marcado; não implementa liquidação ou reinício automático.
Usa filtros atuais públicos de preço/lote/mínimo. Não reproduz todos os filtros e a fila da Binance.
Compra/venda reposta somente após preenchimento completo, usando um evento posterior.
Agressor derivado do campo m: comprador maker significa agressor vendedor. Participação de 10% é hipótese.
Ao fim da amostra, cancela pendências. Não desconta liquidação das posições nem atribui rendimento anual.
Uma amostra sem preenchimentos é um resultado operacional válido; não se estreita a grade para forçar trades.
Fonte técnica: https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market

Execução UTC (pode usar entrada salva): 2026-10-19T00:10:13.055282+00:00
