"""Public aggregate-trade smoke replay; no account credentials or transactions."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import urllib.request
from grid_controller import GridEpisode
from limit_simulator import D, LimitBook


def validate_tape(rows):
    if not isinstance(rows, list) or len(rows) < 2:
        raise ValueError('Replay exige pelo menos dois eventos')
    for row in rows:
        if any(type(row[k]) is not int for k in ('a', 'T')) or type(row['m']) is not bool:
            raise ValueError('Identificador, horário ou agressor inválidos')
        if D(row['p']) <= 0 or D(row['q']) <= 0:
            raise ValueError('Preço/volume inválidos')
    for a, b in zip(rows, rows[1:]):
        if b['a'] != a['a']+1 or b['T'] < a['T']:
            raise ValueError('Negócios fora de ordem, repetidos ou com lacunas de ID')


def symbol_filters(info, symbol):
    entry = next(row for row in info['symbols'] if row['symbol']==symbol)
    if entry['status'] != 'TRADING':
        raise ValueError('Par indisponível')
    f = {row['filterType']: row for row in entry['filters']}
    price, lot = f['PRICE_FILTER'], f['LOT_SIZE']
    minimum = max(D(f.get('MIN_NOTIONAL', {}).get('minNotional', 0)),
                  D(f.get('NOTIONAL', {}).get('minNotional', 0)))
    return {symbol: dict(tick=price['tickSize'], step=lot['stepSize'], min_qty=lot['minQty'],
        max_qty=lot['maxQty'], min_price=price['minPrice'], max_price=price['maxPrice'],
        min_notional=str(minimum), max_orders=int(f.get('MAX_NUM_ORDERS', {}).get('maxNumOrders', 20)))}


def replay(rows, filters, symbol='BTCUSDT', stop_requested=None):
    validate_tape(rows)  # Preflight integrity only; prices after the first event never set the grid.
    book = LimitBook({symbol: rows[0]['p']}, filters, cash=1000, stop_requested=stop_requested)
    book.trade(rows[0]['a'], symbol, rows[0]['p'], 0, 'SELL' if rows[0]['m'] else 'BUY')
    episode = GridEpisode(book, symbol)
    for row in rows[1:]:
        episode.advance(row['a'], row['p'], row['q'], 'SELL' if row['m'] else 'BUY')
    marked = book.summary()
    # Working orders are canceled at replay cutoff; open inventory is valued, not liquidated.
    active_at_cutoff = marked['active_orders']
    reserved_at_cutoff = marked['reserved_cash']
    book.cancel_all('fim do replay')
    return dict(capital_usdt=1000, symbol=symbol, smoke_test_only=True, adopted=False,
                approved_for_trading=False, first_time=rows[0]['T'], last_time=rows[-1]['T'],
                first_id=rows[0]['a'], last_id=rows[-1]['a'], events=len(rows),
                active_at_cutoff=active_at_cutoff, reserved_at_cutoff=reserved_at_cutoff,
                summary=book.summary(), completed_cycles=episode.completed_cycles,
                episode_closed=episode.closed, placement_failures=episode.failures,
                fills=book.fills, filters=filters, anchor=episode.anchor,
                parameters=dict(spacing='.005', levels=4, order_usdt=25, participation='.1', fee='.001'),
                data_hash=hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest())


def main():
    symbol = 'BTCUSDT'
    def get(path):
        with urllib.request.urlopen('https://data-api.binance.vision/api/v3/'+path, timeout=30) as response:
            return json.load(response)
    filters = symbol_filters(get('exchangeInfo?symbol='+symbol), symbol)
    rows = get('aggTrades?symbol='+symbol+'&limit=1000')
    report = replay(rows, filters)
    report['created'] = dt.datetime.now(dt.timezone.utc).isoformat()
    root = Path(__file__).resolve().parent
    report['code_hash'] = hashlib.sha256(b''.join((root/name).read_bytes() for name in
        ('grid_replay.py', 'grid_controller.py', 'limit_simulator.py'))).hexdigest()
    output = root/'reports/2026-10-18-grid-replay.json'
    output.write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
    s = report['summary']
    seconds = (report['last_time']-report['first_time'])/1000
    lines = ['# Replay operacional do Grid', '',
        '**Amostra curta de negócios públicos reais; preenchimentos e carteira simulados. Não valida rentabilidade.**', '',
        f"Capital fictício: 1.000 USDT. Par: {symbol}. Eventos: {report['events']}. Duração: {seconds:.3f} segundos.",
        f"Patrimônio marcado: {s['equity']:.5f} USDT. Taxas simuladas: {s['fees']:.5f} USDT.",
        f"Preenchimentos: {s['fills']}. Ciclos completos compra/venda: {report['completed_cycles']}.",
        f"Ordens abertas antes do encerramento: {report['active_at_cutoff']}. Reserva antes do encerramento: {report['reserved_at_cutoff']:.5f} USDT.",
        f"Ordens após cancelamento final: {s['active_orders']}. Episódio rompido/travado: {report['episode_closed']}.", '',
        'Faixa e degraus definidos apenas pelo primeiro negócio, sem ajuste após consultar os resultados.',
        'Ao romper ±3% da âncora, cancela ordens e mantém inventário marcado; não implementa liquidação ou reinício automático.',
        'Usa filtros atuais públicos de preço/lote/mínimo. Não reproduz todos os filtros e a fila da Binance.',
        'Compra/venda reposta somente após preenchimento completo, usando um evento posterior.',
        'Agressor derivado do campo m: comprador maker significa agressor vendedor. Participação de 10% é hipótese.',
        'Ao fim da amostra, cancela pendências. Não desconta liquidação das posições nem atribui rendimento anual.',
        'Uma amostra sem preenchimentos é um resultado operacional válido; não se estreita a grade para forçar trades.',
        'Fonte técnica: https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market',
        '', 'Consulta UTC: '+report['created']]
    output.with_suffix('.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
