"""Offline exploratory candle model; never authorizes trading or edits paper state.

Signals use closed bars and execute at the NEXT open. Intrabar ambiguity selects
the stop first. No order-book/queue reconstruction or historical exchange filters.
"""
from dataclasses import asdict, replace
import hashlib
import json
import math
from pathlib import Path
import statistics
import uuid

from .config import load_settings
from .data import load_history, interval
from .strategy import analyze


def run(history, settings, *, entry_mask=None):
    """One fixed parameter trial. Float research arithmetic, not execution ledger."""
    signals = analyze(history, settings)  # Also validates causal bar sequence.
    bars = history.candles
    # Optional offline research filter only suppresses existing EMA entries.
    # It cannot introduce entries, change exits or authorize the paper engine.
    if entry_mask is not None and (not isinstance(entry_mask,(list,tuple)) or
            len(entry_mask)!=len(bars) or any(type(x) is not bool for x in entry_mask)):
        raise ValueError('Máscara de pesquisa inválida.')
    warmup = max(3 * settings.ema_trend, settings.atr_period + 1)
    if len(bars) <= warmup:
        raise ValueError('Histórico insuficiente após aquecimento.')
    cash = initial = float(settings.capital)
    fee, slip = float(settings.fee_rate), float(settings.slippage_rate)
    qty = cost = stop = target = 0.0
    peak = day_base = initial
    day = None
    daily_halt = permanent_halt = False
    trades, curve, returns = [], [], []
    fees = 0.0
    max_dd = 0.0
    previous = initial

    def sell(price, reason, timestamp):
        nonlocal cash, qty, cost, fees
        proceeds = qty * price
        charge = proceeds * fee
        pnl = proceeds - charge - cost
        cash += proceeds - charge
        fees += charge
        trades.append({'exit_ms': timestamp, 'reason': reason, 'pnl': pnl})
        qty = cost = 0.0

    for i in range(warmup, len(bars)):
        b = bars[i]
        signal = signals[i - 1].action
        if signal=='ENTER_LONG' and entry_mask is not None and not entry_mask[i-1]:
            signal='HOLD'
        mark_open = cash + qty * b.open * (1 - slip) * (1 - fee)
        current_day = b.open_ms // 86_400_000
        if day != current_day:
            day, day_base, daily_halt = current_day, mark_open, False
        peak = max(peak, mark_open)
        daily_halt |= mark_open <= day_base * (1 - float(settings.daily_loss_limit))
        permanent_halt |= mark_open <= peak * (1 - float(settings.max_drawdown))
        # Existing position: gaps execute worse than the stop, never at a
        # guaranteed stop price. Model uses market exits, unlike paper LIMITs.
        if qty:
            if b.open <= stop:
                sell(b.open * (1 - slip), 'STOP_GAP', b.open_ms)
            elif signal == 'EXIT_LONG':
                sell(b.open * (1 - slip), 'SIGNAL', b.open_ms)
        elif signal == 'ENTER_LONG' and not daily_halt and not permanent_halt:
            entry = b.open * (1 + slip)
            stop = entry * (1 - float(settings.stop_loss_fraction))
            target = entry * (1 + float(settings.take_profit_fraction))
            risk_unit = entry * (1 + fee) - stop * (1 - slip) * (1 - fee)
            risk_budget = min(mark_open * float(settings.risk_per_trade),
                              max(0, mark_open - day_base * (1 - float(settings.daily_loss_limit))),
                              max(0, mark_open - peak * (1 - float(settings.max_drawdown))))
            qty = min(cash, float(settings.max_order_notional), risk_budget / risk_unit * entry * (1 + fee)) / (entry * (1 + fee))
            cost = qty * entry * (1 + fee)
            fees += qty * entry * fee
            cash -= cost
        if qty:
            if b.low <= stop:
                sell(min(b.open, stop) * (1 - slip), 'STOP', b.open_ms)
            elif b.high >= target:
                sell(target * (1 - slip), 'TARGET', b.open_ms)
        equity = cash + qty * b.close * (1 - slip) * (1 - fee)
        peak = max(peak, equity)
        max_dd = max(max_dd, 1 - equity / peak)
        daily_halt |= equity <= day_base * (1 - float(settings.daily_loss_limit))
        permanent_halt |= max_dd >= float(settings.max_drawdown)
        returns.append(equity / previous - 1)
        previous = equity
        curve.append({'close_ms': b.open_ms + interval(settings.symbol, settings.timeframe), 'equity': equity})
    # Explicit final hypothetical liquidation; not silently counted as an open gain.
    if qty:
        sell(bars[-1].close * (1 - slip), 'END_LIQUIDATION', history.end_ms)
    wins = sum(t['pnl'] for t in trades if t['pnl'] > 0)
    losses = -sum(t['pnl'] for t in trades if t['pnl'] < 0)
    sigma = statistics.stdev(returns) if len(returns) > 1 else 0
    periods = 365.25 * 86_400_000 / interval(settings.symbol, settings.timeframe)
    benchmark = bars[-1].close * (1 - slip) * (1 - fee) / (bars[warmup].open * (1 + slip) * (1 + fee)) - 1
    return {'approved': False, 'scope': 'EXPLORATORY_CANDLE_MODEL',
            'capital': initial, 'final_equity': cash, 'net_return': cash / initial - 1,
            'buy_hold_return': benchmark, 'max_drawdown': max_dd,
            'closed_trades': len(trades), 'win_rate': sum(t['pnl'] > 0 for t in trades) / len(trades) if trades else None,
            'profit_factor': wins / losses if losses else None,
            'sharpe_zero_rf': statistics.mean(returns) / sigma * math.sqrt(periods) if sigma else None,
            'fees': fees, 'drawdown_latched': permanent_halt, 'warmup_bars': warmup,
            'trades': trades, 'equity_curve': curve,
            'limitations': ['No historical LOT_SIZE/MIN_NOTIONAL; fractional units may be infeasible with 20 USDT.',
                           'No spread, partial fills, queue or latency reconstruction; slippage is an assumption.',
                           'Stop first when stop and target occur within the same bar; intrabar path unknown.',
                           'Daily/drawdown controls observe opens and closes, not continuous intrabar equity.',
                           'One exploratory trial, no independent walk-forward approval or statistical significance.',
                           'Synthetic market exits differ from the active paper LIMIT engine.']}


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Backtest exploratório offline; nenhuma ordem real.')
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--order-budget', default='6')
    args = parser.parse_args()
    from decimal import Decimal
    cfg = replace(load_settings(), mode='backtest', max_order_notional=Decimal(args.order_budget))
    history = load_history(args.csv)
    result = run(history, cfg)
    result['settings'] = {k: str(v) for k, v in asdict(cfg).items()}
    result['csv_sha256'] = hashlib.sha256(args.csv.read_bytes()).hexdigest()
    result['model_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    folder = Path(__file__).resolve().parent.parent / 'reports/local/spot-backtest'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (uuid.uuid4().hex + '.json')
    with path.open('x', encoding='utf-8') as output:
        json.dump(result, output, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({k: v for k, v in result.items() if k not in ('equity_curve', 'trades', 'settings')}, ensure_ascii=False, indent=2, allow_nan=False))
    print('Relatório: ' + str(path))


if __name__ == '__main__':
    main()
