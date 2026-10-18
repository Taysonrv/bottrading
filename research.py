"""Fixed-rule comparisons with chronological evaluation; no parameter fitting."""
import math
import statistics
import time
import urllib.parse
import execution

HOUR = 3_600_000
STRATEGIES = ('regime_v1', 'trend_v1', 'breakout_v1')


def check_rows(rows, expected=None, step=HOUR):
    if expected is not None and len(rows) != expected:
        raise ValueError('Histórico não cobre todo o período solicitado')
    for row in rows:
        if any(not math.isfinite(row[k]) or row[k] <= 0 for k in ('open', 'high', 'low', 'close')):
            raise ValueError('Preço inválido')
        if row['low'] > min(row['open'], row['close']) or row['high'] < max(row['open'], row['close']):
            raise ValueError('OHLC inconsistente')
    if any(b['open_time'] - a['open_time'] != step for a, b in zip(rows, rows[1:])):
        raise ValueError('Histórico com lacunas ou duplicatas')


def download(symbol, days, request, end=None):
    # UTC hour boundary fixes both endpoints; the current open candle is excluded.
    end = int(time.time() * 1000) // HOUR * HOUR if end is None else end
    if type(end) is not int or end % HOUR:
        raise ValueError('Horário final precisa ser uma hora UTC fechada')
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


def backtest(histories, start, end, config, strategy, base_signal, stress=1, initial_exposure=0., risk_policy='freeze', stop_requested=None, target_at=None):
    """One shared wallet, signal at t-1 close, fill at t open, low-price risk check."""
    symbols = list(histories)
    if risk_policy not in ('freeze', 'reduce'):
        raise ValueError('Política de risco desconhecida')
    if not 0 <= initial_exposure <= 1:
        raise ValueError('Exposição inicial inválida')
    cash = 1000.0 * (1 - initial_exposure)
    positions = {s: 1000.0 * initial_exposure / len(symbols) / histories[s][start]['open'] for s in symbols}
    peak, worst, trades, costs = 1000.0, 0.0, 0, 0.0
    halted = False
    stopped, halt_at, defensive_orders, defensive_buys = False, None, 0, 0
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
        reduce_ready = halted  # A newly observed trigger cannot fill at an earlier/same opening.
        opens = {s: histories[s][i]['open'] for s in symbols}
        risk(mark(opens))
        if halted and halt_at is None:
            halt_at = histories[symbols[0]][i]['open_time']
        for symbol in symbols:
            if stopped or (halted and (risk_policy == 'freeze' or not reduce_ready)):
                break
            equity = mark(opens)
            risk(equity)  # Fees from earlier orders can trigger a block.
            if halted and halt_at is None:
                halt_at = histories[symbols[0]][i]['open_time']
            if halted and (risk_policy == 'freeze' or not reduce_ready):
                break
            fraction = (0. if halted else target_at(symbol, i) if target_at else
                        target(closes[symbol][max(0, i - 200):i], strategy, base_signal)[1])
            exposure = sum(positions[s] * opens[s] for s in symbols)
            delta = execution.plan(equity, cash, positions[symbol], opens[symbol], opens[symbol],
                                   exposure, fraction, config, fee, slip)
            if stop_requested and stop_requested():
                stopped = True
                break
            if halted and delta > 0:
                raise ValueError('Saída defensiva não pode aumentar exposição')
            cash, positions[symbol], order = fill(cash, positions[symbol], opens[symbol], delta, fee, slip)
            if order:
                trades += 1
                costs += order['fee'] + order['slippage_cost']
                if halted:
                    defensive_orders += 1
                    defensive_buys += order['side'] == 'BUY'
        # Conservative: assumes all assets' hourly lows occur together.
        risk(mark({s: histories[s][i]['low'] for s in symbols}))
        risk(mark({s: histories[s][i]['close'] for s in symbols}))
        if halted and halt_at is None:
            halt_at = histories[symbols[0]][i]['time']
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
              'initial_exposure': initial_exposure,
              'risk_policy': risk_policy, 'halt_at': halt_at, 'manually_stopped': stopped,
              'defensive_orders': defensive_orders, 'defensive_buys': defensive_buys,
              'remaining_exposure_usdt': sum(positions[s] * histories[s][end - 1]['close'] for s in symbols),
              'last_candle': histories[symbols[0]][end - 1]['time']}
    result['passed'] = (result['return'] > max(0, benchmark) and worst < .15 and trades >= 3 and not halted and not stopped)
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
        existing = backtest(histories, boundary, count, config, strategy, base_signal, initial_exposure=.8)
        continuous = backtest(histories, 200, count, config, strategy, base_signal)
        defensive = {'adopted': False, 'freeze': continuous,
                     'reduce': backtest(histories, 200, count, config, strategy, base_signal, risk_policy='reduce'),
                     'reduce_stress': backtest(histories, 200, count, config, strategy, base_signal, stress=2, risk_policy='reduce'),
                     'existing_freeze': backtest(histories, 200, count, config, strategy, base_signal, initial_exposure=.8),
                     'existing_reduce': backtest(histories, 200, count, config, strategy, base_signal, initial_exposure=.8, risk_policy='reduce')}
        comparisons[strategy] = {'symbols': individual, 'portfolio_folds': portfolio,
                                 'portfolio_holdout': holdout, 'portfolio_stress': stress,
                                 'existing_positions_holdout': existing, 'continuous_portfolio': continuous,
                                 'defensive_research': defensive,
                                 'passed': all(f['passed'] for f in portfolio + [holdout, stress, existing, continuous]) and
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
        rows.append(('Carteira com posições iniciais (80%)', comparison['existing_positions_holdout'], comparison['existing_positions_holdout']['passed']))
        rows.append(('Carteira contínua (período completo)', comparison['continuous_portfolio'], comparison['continuous_portfolio']['passed']))
        for symbol, result, passed in rows:
            lines.append(f"| {name} | {symbol} | {result['return']:.2%} | {result['benchmark']:.2%} | {result['drawdown']:.2%} | {'Sim' if passed else 'Não'} |")
    lines += ['', 'Tabela: período final reservado (25% após aquecimento), exceto a linha contínua que usa todo o período. Aprovação exige também passar nas três janelas anteriores, com custos dobrados, com posições iniciais e sem reiniciar a carteira ao longo do período completo.',
              '', 'O cenário de posições iniciais assume 80% do capital já investido, com pesos iguais pelo preço de abertura. Não representa a carteira real nem inclui seu custo histórico. A redução de exposição continua limitada por ordem; não é instantânea.',
              '', 'Benchmark principal: comprar e manter com 100% do capital (pesos iguais na carteira). O JSON também mostra benchmark proporcional à exposição.',
              '', 'Regras e parâmetros fixos; não houve otimização. Reutilizar este período para ajustar regras transforma-o em desenvolvimento; será necessário um novo período futuro para confirmar.',
              '', 'Execução histórica: abertura seguinte ao sinal, taxas/slippage estimados, limites compartilhados e avaliação conservadora das mínimas horárias. Não modela livro completo nem garante perdas limitadas a 15%.']
    return '\n'.join(lines) + '\n'


def defensive_markdown(report):
    lines = ['# Saída defensiva — experimento histórico', '',
             'Pesquisa separada: nenhuma mudança no bot ativo ou nos critérios de aprovação.', '',
             '| Estratégia | Cenário contínuo | Retorno | Drawdown | Vendas defensivas | Exposição final (USDT) |',
             '|---|---|---:|---:|---:|---:|']
    labels = {'freeze': 'Bloqueio atual', 'reduce': 'Saída gradual', 'reduce_stress': 'Saída gradual / custos dobrados',
              'existing_freeze': '80% investido / bloqueio atual', 'existing_reduce': '80% investido / saída gradual'}
    for strategy, comparison in report['comparisons'].items():
        for key, label in labels.items():
            r = comparison['defensive_research'][key]
            lines.append(f"| {strategy} | {label} | {r['return']:.2%} | {r['drawdown']:.2%} | {r['defensive_orders']} | {r['remaining_exposure_usdt']:.2f} |")
    lines += ['', 'Mesmo histórico e regras de entrada para as políticas comparadas. O cenário experimental só vende após o gatilho de 15%; não volta a comprar.',
              'Vendas simuladas continuam limitadas por ordem e ocorrem na abertura seguinte à detecção. Lacunas de preço, custos e o tempo para reduzir posições podem fazer o drawdown ultrapassar 15%.',
              'STOP sempre prevalece. Não se assume liquidação instantânea. Resíduos abaixo do mínimo de ordem podem permanecer.',
              'Um resultado melhor neste histórico não valida a política em dados futuros. Nenhuma estratégia foi liberada por esse experimento.']
    return '\n'.join(lines) + '\n'
