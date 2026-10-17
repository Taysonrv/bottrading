"""Fixed-rule comparisons with chronological evaluation; no parameter fitting."""
import math
import statistics
import time
import urllib.parse

HOUR = 3_600_000
STRATEGIES = ('regime_v1', 'trend_v1', 'breakout_v1')


def check_rows(rows, expected=None):
    if expected is not None and len(rows) != expected:
        raise ValueError('Histórico não cobre todo o período solicitado')
    for row in rows:
        if any(not math.isfinite(row[k]) or row[k] <= 0 for k in ('open', 'high', 'low', 'close')):
            raise ValueError('Preço inválido')
        if row['low'] > min(row['open'], row['close']) or row['high'] < max(row['open'], row['close']):
            raise ValueError('OHLC inconsistente')
    if any(b['open_time'] - a['open_time'] != HOUR for a, b in zip(rows, rows[1:])):
        raise ValueError('Histórico com lacunas ou duplicatas')


def download(symbol, days, request):
    # UTC hour boundary fixes both endpoints; the current open candle is excluded.
    end = int(time.time() * 1000) // HOUR * HOUR
    start = end - days * 24 * HOUR
    cursor, rows = start, []
    while cursor < end:
        query = urllib.parse.urlencode({'symbol': symbol, 'interval': '1h', 'limit': 1000,
                                       'startTime': cursor, 'endTime': end - 1})
        page = request('https://data-api.binance.vision/api/v3/klines?' + query)
        if not isinstance(page, list) or not page:
            raise ValueError('Resposta vazia ou inválida da Binance')
        batch = [{'open_time': int(r[0]), 'time': int(r[6]), 'open': float(r[1]),
                  'high': float(r[2]), 'low': float(r[3]), 'close': float(r[4])} for r in page]
        if batch[0]['open_time'] != cursor or batch[-1]['open_time'] >= end:
            raise ValueError('Resposta fora do período solicitado')
        rows.extend(batch)
        cursor = batch[-1]['open_time'] + HOUR
    check_rows(rows, days * 24)
    return rows


def target(prices, strategy, base_signal):
    if strategy not in STRATEGIES:
        raise ValueError('Estratégia desconhecida')
    regime, original = base_signal(prices)
    if strategy == 'regime_v1' or len(prices) < 200:
        return regime, original
    if regime in ('nervoso', 'queda_forte'):
        return regime, 0.0
    if strategy == 'trend_v1':
        return regime, float(prices[-1] > statistics.mean(prices[-48:]) > statistics.mean(prices[-200:]))
    # Near a prior 96-hour high in an uptrend. Fixed threshold, never optimized here.
    return regime, float(prices[-1] >= max(prices[-97:-1]) * 0.998 and
                         prices[-1] > statistics.mean(prices[-200:]))


def fill(cash, units, reference, delta, fee, slippage, minimum=10):
    """Signed reference notional; slippage affects fill price, fees affect cash."""
    if delta > 0:
        price = reference * (1 + slippage)
        quantity = min(delta / reference, cash / (price * (1 + fee)))
    else:
        price = reference * (1 - slippage)
        quantity = -min(units, -delta / reference)
    notional = abs(quantity) * price
    if notional < minimum:
        return cash, units, None
    charge = notional * fee
    cash -= quantity * price + charge
    units += quantity
    if cash < -1e-8 or units < -1e-8:
        raise ValueError('Saldo negativo na simulação')
    return max(0.0, cash), max(0.0, units), {
        'side': 'BUY' if quantity > 0 else 'SELL', 'quantity': abs(quantity),
        'price': price, 'fee': charge, 'slippage_cost': abs(quantity) * abs(price - reference)}


def backtest(histories, start, end, config, strategy, base_signal, stress=1):
    """One shared wallet, signal at t-1 close, fill at t open, low-price risk check."""
    symbols = list(histories)
    cash, positions = 1000.0, dict.fromkeys(symbols, 0.0)
    peak, worst, trades, costs = 1000.0, 0.0, 0, 0.0
    halted = False
    fee, slip = config['fee_rate'] * stress, config['slippage_rate'] * stress
    closes = {s: [r['close'] for r in rows] for s, rows in histories.items()}
    def mark(prices):
        return cash + sum(positions[s] * prices[s] for s in symbols)
    def risk(value):
        nonlocal peak, worst, halted
        peak = max(peak, value)
        worst = max(worst, 1 - value / peak)
        halted = halted or worst >= .15
    for i in range(start, end):
        opens = {s: histories[s][i]['open'] for s in symbols}
        risk(mark(opens))
        for symbol in symbols:
            if halted:
                break
            equity = mark(opens)
            risk(equity)  # Fees from earlier orders can trigger a block.
            if halted:
                break
            fraction = target(closes[symbol][max(0, i - 200):i], strategy, base_signal)[1]
            delta = equity * config['max_symbol_fraction'] * fraction - positions[symbol] * opens[symbol]
            cap = equity * config['max_order_fraction']
            delta = max(-cap, min(cap, delta))
            if delta > 0:
                exposure = sum(positions[s] * opens[s] for s in symbols)
                delta = min(delta, max(0, equity * config['max_total_fraction'] - exposure))
            cash, positions[symbol], order = fill(cash, positions[symbol], opens[symbol], delta, fee, slip)
            if order:
                trades += 1
                costs += order['fee'] + order['slippage_cost']
        # Conservative: assumes all assets' hourly lows occur together.
        risk(mark({s: histories[s][i]['low'] for s in symbols}))
        risk(mark({s: histories[s][i]['close'] for s in symbols}))
    # Value all remaining inventory at net sale proceeds, without bypassing the kill switch.
    terminal = cash + sum(positions[s] * histories[s][end - 1]['close'] * (1 - slip) * (1 - fee) for s in symbols)
    risk(terminal)
    benchmark = sum(histories[s][end - 1]['close'] * (1 - slip) * (1 - fee) /
                    (histories[s][start]['open'] * (1 + slip) * (1 + fee)) for s in symbols) / len(symbols) - 1
    matched_fraction = min(config['max_total_fraction'], config['max_symbol_fraction'] * len(symbols))
    result = {'return': terminal / 1000 - 1, 'benchmark': benchmark,
              'matched_exposure_benchmark': benchmark * matched_fraction,
              'drawdown': worst, 'trades': trades, 'costs_usdt': costs,
              'halted': halted, 'first_candle': histories[symbols[0]][start]['open_time'],
              'last_candle': histories[symbols[0]][end - 1]['time']}
    result['passed'] = (result['return'] > max(0, benchmark) and worst < .15 and trades >= 3 and not halted)
    return result


def evaluate(histories, config, base_signal):
    count = len(next(iter(histories.values())))
    timestamps = [r['open_time'] for r in next(iter(histories.values()))]
    if any([r['open_time'] for r in rows] != timestamps for rows in histories.values()):
        raise ValueError('Históricos dos ativos não estão alinhados')
    boundary = 200 + (count - 200) * 3 // 4
    width = (boundary - 200) // 3
    windows = [(200 + i * width, boundary if i == 2 else 200 + (i + 1) * width) for i in range(3)]
    comparisons = {}
    for strategy in STRATEGIES:
        individual = {}
        for symbol, rows in histories.items():
            folds = [backtest({symbol: rows}, a, b, config, strategy, base_signal) for a, b in windows]
            holdout = backtest({symbol: rows}, boundary, count, config, strategy, base_signal)
            stress = backtest({symbol: rows}, boundary, count, config, strategy, base_signal, stress=2)
            individual[symbol] = {'folds': folds, 'holdout': holdout, 'stress': stress,
                                  'passed': all(f['passed'] for f in folds + [holdout, stress])}
        portfolio = [backtest(histories, a, b, config, strategy, base_signal) for a, b in windows]
        holdout = backtest(histories, boundary, count, config, strategy, base_signal)
        stress = backtest(histories, boundary, count, config, strategy, base_signal, stress=2)
        comparisons[strategy] = {'symbols': individual, 'portfolio_folds': portfolio,
                                 'portfolio_holdout': holdout, 'portfolio_stress': stress,
                                 'passed': all(f['passed'] for f in portfolio + [holdout, stress]) and
                                 all(r['passed'] for r in individual.values())}
    return comparisons


def markdown(report):
    lines = ['# Comparação histórica — simulação', '',
             f"Estratégia configurada: `{report['active_strategy']}`. Nenhuma seleção automática.", '',
             '| Estratégia | Ativo/carteira | Retorno final | Comprar e manter | Drawdown | Aprovada |',
             '|---|---|---:|---:|---:|---|']
    for name, comparison in report['comparisons'].items():
        rows = [(s, r['holdout'], r['passed']) for s, r in comparison['symbols'].items()]
        rows.append(('Carteira', comparison['portfolio_holdout'], comparison['passed']))
        for symbol, result, passed in rows:
            lines.append(f"| {name} | {symbol} | {result['return']:.2%} | {result['benchmark']:.2%} | {result['drawdown']:.2%} | {'Sim' if passed else 'Não'} |")
    lines += ['', 'Tabela: período final reservado (25% após aquecimento). Aprovação exige também passar nas três janelas anteriores e com custos dobrados.',
              '', 'Benchmark principal: comprar e manter com 100% do capital (pesos iguais na carteira). O JSON também mostra benchmark proporcional à exposição.',
              '', 'Regras e parâmetros fixos; não houve otimização. Reutilizar este período para ajustar regras transforma-o em desenvolvimento; será necessário um novo período futuro para confirmar.',
              '', 'Execução histórica: abertura seguinte ao sinal, taxas/slippage estimados, limites compartilhados e avaliação conservadora das mínimas horárias. Não modela livro completo nem garante perdas limitadas a 15%.']
    return '\n'.join(lines) + '\n'
