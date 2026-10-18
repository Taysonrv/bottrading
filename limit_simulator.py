"""Offline limit-order simulator. No network, credentials or live-order adapter."""
from decimal import Decimal, ROUND_DOWN


def D(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError('Número não finito')
    return result


class LimitBook:
    def __init__(self, prices, filters, cash=1000, positions=None, fee='.001', participation='.1',
                 stop_requested=None):
        self.prices = {s: D(p) for s, p in prices.items()}
        if not self.prices or any(p <= 0 for p in self.prices.values()):
            raise ValueError('Preços inválidos')
        self.filters = filters
        self.cash = D(cash)
        self.positions = {s: D((positions or {}).get(s, 0)) for s in prices}
        self.fee, self.participation = D(fee), D(participation)
        if self.cash < 0 or any(q < 0 for q in self.positions.values()) or not 0 <= self.fee < 1 or not 0 < self.participation <= 1:
            raise ValueError('Saldo, taxa ou participação inválidos')
        self.orders, self.fills, self.events = {}, [], []
        self.sequence, self.next_id = 0, 1
        self.halted, self.stopped = False, False
        self.peak, self.drawdown, self.fees = self.equity(), D(0), D(0)
        if self.peak <= 0:
            raise ValueError('Carteira vazia')
        self.stop_requested = stop_requested or (lambda: False)

    def equity(self):
        return self.cash + sum(q*self.prices[s] for s, q in self.positions.items())

    def active(self):
        return [o for o in self.orders.values() if o['status'] in ('NEW', 'PARTIALLY_FILLED')]

    def reserved_cash(self):
        return sum((o['remaining']*o['price']*(1+self.fee) for o in self.active() if o['side']=='BUY'), D(0))

    def reserved_units(self, symbol):
        return sum((o['remaining'] for o in self.active() if o['side']=='SELL' and o['symbol']==symbol), D(0))

    def cancel(self, order_id, reason='cancelamento'):
        order = self.orders[order_id]
        if order in self.active():
            order['status'] = 'CANCELED'
            self.events.append({'kind': 'cancel', 'order': order_id, 'reason': reason})

    def cancel_all(self, reason):
        for order in list(self.active()):
            self.cancel(order['id'], reason)

    def guard(self):
        self.stopped = self.stopped or bool(self.stop_requested())
        value = self.equity()
        self.peak = max(self.peak, value)
        self.drawdown = max(self.drawdown, 1-value/self.peak)
        self.halted = self.halted or self.drawdown >= D('.15')
        if self.stopped or self.halted:
            self.cancel_all('STOP' if self.stopped else 'drawdown')
            return False
        return True

    def _within_budget(self, orders):
        """Worst-case current marks if all reserved buys execute at their limits."""
        buys = [o for o in orders if o['side']=='BUY']
        loss = sum((max(D(0), o['price']*(1+self.fee)-self.prices[o['symbol']])*o['remaining']
                    for o in buys), D(0))
        equity = self.equity()-loss
        holdings = {s: q*self.prices[s] for s, q in self.positions.items()}
        for order in buys:
            holdings[order['symbol']] += order['remaining']*self.prices[order['symbol']]
        return (equity > 0 and sum(holdings.values()) <= equity*D('.6') and
                all(v <= equity*D('.2') for v in holdings.values()))

    def place(self, symbol, side, price, quantity):
        if not self.guard():
            raise ValueError('Trava ativa')
        if symbol not in self.prices or side not in ('BUY', 'SELL'):
            raise ValueError('Ativo/lado inválido')
        price, quantity = D(price), D(quantity)
        f = self.filters[symbol]
        tick, step = D(f['tick']), D(f['step'])
        if tick <= 0 or step <= 0 or price <= 0 or quantity <= 0:
            raise ValueError('Preço/quantidade inválidos')
        # Reject misaligned prices; round quantity down, never increase exposure.
        if price % tick:
            raise ValueError('Preço fora do tick')
        quantity = (quantity/step).to_integral_value(rounding=ROUND_DOWN)*step
        if not D(f['min_qty']) <= quantity <= D(f['max_qty']) or quantity*price < D(f['min_notional']):
            raise ValueError('Quantidade ou valor fora dos filtros')
        if not D(f['min_price']) <= price <= D(f['max_price']):
            raise ValueError('Preço fora dos limites')
        if len([o for o in self.active() if o['symbol']==symbol]) >= f['max_orders']:
            raise ValueError('Limite de ordens pendentes')
        if quantity*price*(1+self.fee) > self.equity()*D('.05'):
            raise ValueError('Limite de 5% por ordem')
        # This model supports passive GTC only; no synthetic instantaneous taker fills.
        if (side=='BUY' and price >= self.prices[symbol]) or (side=='SELL' and price <= self.prices[symbol]):
            raise ValueError('Preço não passivo em relação à última negociação')
        order = dict(id=self.next_id, symbol=symbol, side=side, price=price, quantity=quantity,
                     remaining=quantity, status='NEW', submitted_after=self.sequence)
        if side=='BUY':
            if quantity*price*(1+self.fee) > self.cash-self.reserved_cash():
                raise ValueError('Saldo livre insuficiente')
            if not self._within_budget(self.active()+[order]):
                raise ValueError('Exposição reservada excede limite')
        elif quantity > self.positions[symbol]-self.reserved_units(symbol):
            raise ValueError('Ativo livre insuficiente')
        self.orders[order['id']] = order
        self.next_id += 1
        return order['id']

    def trade(self, sequence, symbol, price, quantity, aggressor):
        """Strict price-through plus explicit aggressive volume, capped participation.

        Touch alone never fills. Later fills at the resting limit (no price improvement).
        The participation cap is a modeling assumption, not a measured queue position.
        """
        price, quantity = D(price), D(quantity)
        if type(sequence) is not int or sequence <= self.sequence or symbol not in self.prices or price <= 0 or quantity < 0 or aggressor not in ('BUY', 'SELL'):
            raise ValueError('Evento inválido ou fora de ordem')
        self.sequence = sequence
        self.prices[symbol] = price
        if not self.guard():
            return []
        available = quantity*self.participation
        candidates = [o for o in self.active() if o['symbol']==symbol and o['submitted_after'] < sequence
                      and ((o['side']=='BUY' and aggressor=='SELL' and price < o['price']) or
                           (o['side']=='SELL' and aggressor=='BUY' and price > o['price']))]
        candidates.sort(key=lambda o: (-o['price'] if o['side']=='BUY' else o['price'], o['id']))
        filled = []
        for order in candidates:
            if not self.guard():
                break
            if order['side']=='BUY' and not self._within_budget(self.active()):
                self.cancel(order['id'], 'exposição reavaliada')
                continue
            if order['remaining']*order['price']*(1+self.fee) > self.equity()*D('.05'):
                self.cancel(order['id'], 'orçamento reavaliado')
                continue
            step = D(self.filters[symbol]['step'])
            amount = (min(available, order['remaining'])/step).to_integral_value(rounding=ROUND_DOWN)*step
            if amount <= 0:
                continue
            notional, fee = amount*order['price'], amount*order['price']*self.fee
            # Partial executions may be smaller than minNotional; the order was validated at entry.
            self.cash += -notional-fee if order['side']=='BUY' else notional-fee
            self.positions[symbol] += amount if order['side']=='BUY' else -amount
            self.fees += fee
            available -= amount
            order['remaining'] -= amount
            order['status'] = 'FILLED' if order['remaining']==0 else 'PARTIALLY_FILLED'
            item = dict(sequence=sequence, order=order['id'], symbol=symbol, side=order['side'],
                        quantity=amount, price=order['price'], fee=fee, status=order['status'])
            self.fills.append(item)
            filled.append(item)
            self.guard()  # Fees can trigger the risk latch before the next fill.
        self.check_balances()
        return filled

    def check_balances(self):
        if self.cash-self.reserved_cash() < 0 or any(q-self.reserved_units(s) < 0 for s, q in self.positions.items()):
            raise AssertionError('Reserva excede o saldo')

    def summary(self):
        return dict(cash=self.cash, positions=self.positions.copy(), equity=self.equity(),
                    fees=self.fees, reserved_cash=self.reserved_cash(), active_orders=len(self.active()),
                    fills=len(self.fills), stopped=self.stopped, halted=self.halted, drawdown=self.drawdown)


def fixture_filters():
    """Artificial filters for deterministic tests, NOT Binance's current pair rules."""
    return {'BTCUSDT': dict(tick='.01', step='.001', min_qty='.001', max_qty='100',
                           min_notional='10', min_price='.01', max_price='1000000', max_orders=20)}
