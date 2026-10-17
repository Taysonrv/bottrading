"""Shared order sizing for paper trading and historical research."""
import math


def plan(equity, cash, units, bid, reference, exposure, target, config, fee, slippage):
    values = (equity, cash, units, bid, reference, exposure, target, fee, slippage)
    if not all(math.isfinite(v) and v >= 0 for v in values) or bid <= 0 or reference <= 0 or not 0 <= target <= 1 or fee >= 1 or slippage >= 1:
        raise ValueError('Valores inválidos para dimensionar ordem')
    desired = (equity * config['max_symbol_fraction'] * target - units * bid) / bid
    cap = equity * config['max_order_fraction']
    if desired > 0:
        # Cash cost includes adverse fill, fees and (in paper mode) the ask/bid spread.
        cost_per_unit = reference * (1 + slippage) * (1 + fee)
        loss_per_unit = max(0., cost_per_unit - bid)
        total_headroom = max(0., equity * config['max_total_fraction'] - exposure)
        symbol_headroom = max(0., equity * config['max_symbol_fraction'] - units * bid)
        quantity = min(desired, cap / cost_per_unit, cash / cost_per_unit,
                       total_headroom / (bid + config['max_total_fraction'] * loss_per_unit),
                       symbol_headroom / (bid + config['max_symbol_fraction'] * loss_per_unit))
    else:
        gross_per_unit = reference * (1 - slippage) * (1 + fee)
        quantity = -min(-desired, units, cap / gross_per_unit)
    return quantity * reference
