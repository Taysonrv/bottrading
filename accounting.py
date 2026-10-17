"""Average-cost accounting for paper orders; never submits transactions."""
import datetime as dt


def initialize(state, prices):
    if 'accounting' in state:
        return
    equity = state['cash'] + sum(q * prices[s] for s, q in state['positions'].items())
    state['accounting'] = {'started': dt.datetime.now(dt.timezone.utc).isoformat(),
        'initial_equity': equity, 'cost_basis': {s: q * prices[s] for s, q in state['positions'].items()},
        'realized_pnl': 0., 'fees': 0., 'slippage_cost': 0., 'orders': 0,
        'profitable_sales': 0, 'losing_sales': 0,
        'note': 'Posições preexistentes avaliadas pelo bid no início desta medição; não representa seu custo de compra histórico.'}


def record(state, symbol, previous_units, order):
    ledger = state['accounting']
    basis = ledger['cost_basis'].get(symbol, 0.)
    quantity, price, fee = order['quantity'], order['price'], order['fee']
    realized = None
    if order['side'] == 'BUY':
        ledger['cost_basis'][symbol] = basis + quantity * price + fee
    else:
        if previous_units <= 0 or quantity > previous_units + 1e-10:
            raise ValueError('Venda incompatível com posição contabilizada')
        removed = basis * min(1., quantity / previous_units)
        realized = quantity * price - fee - removed
        ledger['cost_basis'][symbol] = max(0., basis - removed)
        ledger['realized_pnl'] += realized
        ledger['profitable_sales'] += realized > 1e-8
        ledger['losing_sales'] += realized < -1e-8
    ledger['fees'] += fee
    ledger['slippage_cost'] += order['slippage_cost']
    ledger['orders'] += 1
    return realized


def mark(state, prices, fee, slippage):
    initialize(state, prices)
    ledger = state['accounting']
    assets, unrealized = [], 0.
    for symbol, units in state['positions'].items():
        value = units * prices[symbol]
        net = value * (1 - slippage) * (1 - fee)
        basis = ledger['cost_basis'].get(symbol, 0.)
        unrealized += net - basis
        assets.append({'symbol': symbol, 'quantity': units, 'cost_basis': basis,
                       'bid_value': value, 'net_liquidation_estimate': net, 'unrealized_pnl': net - basis})
    equity = state['cash'] + sum(a['bid_value'] for a in assets)
    liquidation = state['cash'] + sum(a['net_liquidation_estimate'] for a in assets)
    baseline = ledger['initial_equity']
    report = {'as_of': dt.datetime.now(dt.timezone.utc).isoformat(), 'started': ledger['started'],
        'mode': 'paper', 'cash': state['cash'], 'equity': equity,
        'net_liquidation_estimate': liquidation, 'initial_equity': baseline,
        'total_pnl': liquidation - baseline,
        'return': liquidation / baseline - 1 if baseline else None,
        'realized_pnl': ledger['realized_pnl'], 'unrealized_pnl': unrealized,
        'fees': ledger['fees'], 'slippage_cost': ledger['slippage_cost'], 'orders': ledger['orders'],
        'profitable_sales': ledger['profitable_sales'], 'losing_sales': ledger['losing_sales'],
        'drawdown': max(0., 1 - equity / state['peak']) if state['peak'] else 0.,
        'halted': state['halted'], 'assets': assets, 'note': ledger['note']}
    if abs(report['total_pnl'] - report['realized_pnl'] - unrealized) > max(1e-6, abs(baseline) * 1e-9):
        raise ValueError('Contabilidade não reconciliou com caixa e posições; execução bloqueada')
    state['performance'] = report
    return report


def markdown(report):
    if not report:
        return '# Desempenho em simulação\n\nExecute um ciclo para iniciar a medição.\n'
    lines = ['# Desempenho em simulação', '', f"Cotações observadas em: {report['as_of']}.",
             f"Início da medição: {report['started']}.", '',
             '| Métrica | USDT ou valor |', '|---|---:|']
    for label, key in [('Caixa', 'cash'), ('Patrimônio pelo bid', 'equity'),
                       ('Valor líquido estimado', 'net_liquidation_estimate'),
                       ('Lucro/prejuízo total', 'total_pnl'), ('Realizado líquido', 'realized_pnl'),
                       ('Não realizado líquido estimado', 'unrealized_pnl'), ('Taxas já pagas', 'fees'),
                       ('Slippage já estimado', 'slippage_cost'), ('Ordens simuladas', 'orders')]:
        lines.append(f'| {label} | {report[key]:.4f} |')
    lines += ['', f"Drawdown pelo bid: {report['drawdown']:.2%}. Trava acionada: {report['halted']}.",
              '', report['note'], '',
              'O valor líquido estima custos para encerrar posições; não cria ordens de encerramento.',
              'Taxas e slippage já estão nos resultados: não subtraia esses campos novamente.',
              'Relatório baseado na última medição salva; não confirma que um processo esteja ativo.']
    return '\n'.join(lines) + '\n'
