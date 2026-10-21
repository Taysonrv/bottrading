"""Pure multi-pair feasibility preview; never reserves money or authorizes orders."""
from decimal import Decimal as D, ROUND_FLOOR, ROUND_CEILING, localcontext
from .risk import Rules, amount


def preview(row, rules, bid, ask, *, now_ms, quote_ms, cash=D('20'),
            budget=D('6'), fee=D('.001'), slippage=D('.001'),
            positions=0, pending=0, stopped=False):
    """Fixed one-position policy on hypothetical cash, NOT a risk checkpoint.

    A valid setup must still pass the shared daily/DD risk ledger at execution.
    Spread threshold 0.2% is a research assumption, not a fitted parameter.
    """
    result = dict(symbol=row.get('symbol'), eligible=False, reason='INVALID_INPUT',
                  execution_authorized=False, quantity='0', estimated_cost='0')
    def reject(reason):
        return dict(result, reason=reason)
    if type(now_ms) is not int or type(quote_ms) is not int:
        return reject('INVALID_TIME')
    if type(positions) is not int or type(pending) is not int or min(positions,pending)<0 or type(stopped) is not bool:
        return reject('INVALID_ACCOUNT')
    if stopped: return reject('STOP')
    if positions or pending: return reject('POSITION_OR_ORDER_EXISTS')
    if row.get('status') != 'OK' or row.get('action') != 'ENTER_LONG':
        return reject('NO_ENTRY_SIGNAL')
    close_ms = row.get('candle_close_ms')
    if type(close_ms) is not int or not 0 <= now_ms-close_ms <= 120000:
        return reject('STALE_SIGNAL')
    if not isinstance(rules,Rules) or rules.symbol != row.get('symbol'):
        return reject('INVALID_RULES')
    if not 0 <= now_ms-rules.observed_ms <= 3600000 or not 0 <= now_ms-quote_ms <= 5000:
        return reject('STALE_MARKET_DATA')
    try:
        for value in (bid,ask,cash,budget): amount(value,positive=True)
        for value in (fee,slippage): amount(value)
        if bid>ask or fee>D('.05') or slippage>D('.05'): return reject('INVALID_COSTS_OR_BOOK')
        with localcontext() as ctx:
            ctx.prec=80
            spread=(ask-bid)/((ask+bid)/2)
            if spread>D('.002'): return reject('WIDE_SPREAD')
            entry=(ask*(1+slippage)/rules.price_tick).to_integral_value(rounding=ROUND_CEILING)*rules.price_tick
            if not rules.min_price<=entry<=rules.max_price: return reject('PRICE_FILTER')
            quantity=(min(cash,budget)/(entry*(1+fee))/rules.qty_step).to_integral_value(rounding=ROUND_FLOOR)*rules.qty_step
            quantity=min(quantity,(rules.max_qty/rules.qty_step).to_integral_value(rounding=ROUND_FLOOR)*rules.qty_step)
            notional=quantity*entry
            if quantity<rules.min_qty or not rules.min_notional<=notional<=rules.max_notional:
                return reject('MINIMUM_OR_NOTIONAL_FILTER')
            stop=(entry*D('.98')/rules.price_tick).to_integral_value(rounding=ROUND_FLOOR)*rules.price_tick
            # Estimated 2% stop includes both fees and adverse stop slippage.
            risk=quantity*(entry*(1+fee)-stop*(1-slippage)*(1-fee))
            if risk>cash*D('.01'): return reject('TRADE_RISK_LIMIT')
            return dict(result,eligible=True,reason='FEASIBLE_PREVIEW',quantity=str(quantity),
                        estimated_cost=str(notional*(1+fee)),estimated_stop_loss=str(risk),
                        spread_fraction=str(spread))
    except (ValueError,ArithmeticError,TypeError):
        return reject('INVALID_INPUT')


def choose(previews):
    """Choose at most one by lowest spread, lexical tie-break; no profit score."""
    eligible=[p for p in previews if p.get('eligible') is True]
    return min(eligible,key=lambda p:(D(p['spread_fraction']),p['symbol']))['symbol'] if eligible else None
