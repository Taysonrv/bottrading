"""One fixed Grid episode over an ordered trade tape; offline, no live orders."""
from decimal import ROUND_DOWN, ROUND_UP
from limit_simulator import D


class GridEpisode:
    def __init__(self, book, symbol, spacing='.005', levels=4, order_usdt=25):
        self.book, self.symbol = book, symbol
        self.anchor = book.prices[symbol]
        self.spacing = D(spacing)
        if not D(0) < self.spacing < D('.03') or type(levels) is not int or not 1 <= levels <= 4:
            raise ValueError('Parâmetros do episódio inválidos')
        self.lower, self.upper = self.anchor*D('.97'), self.anchor*D('1.03')
        self.closed, self.completed_cycles = False, 0
        self.mapping, self.failures = {}, []
        tick = D(book.filters[symbol]['tick'])
        for level in range(1, levels+1):
            buy = (self.anchor*(1-self.spacing*level)/tick).to_integral_value(rounding=ROUND_DOWN)*tick
            sell = ((buy+self.anchor*self.spacing)/tick).to_integral_value(rounding=ROUND_UP)*tick
            quantity = D(order_usdt)/(buy*(1+book.fee))
            try:
                oid = book.place(symbol, 'BUY', buy, quantity)
                self.mapping[oid] = (buy, sell)
            except ValueError as error:
                self.failures.append(str(error))

    def advance(self, sequence, price, quantity, aggressor):
        price = D(price)
        if not self.closed and not self.lower <= price <= self.upper:
            self.closed = True
            self.book.cancel_all('ruptura da faixa')
        fills = self.book.trade(sequence, self.symbol, price, quantity, aggressor)
        if self.closed or self.book.halted or self.book.stopped:
            self.closed = True
            return fills
        for fill in fills:
            if fill['status'] != 'FILLED':
                continue
            order = self.book.orders[fill['order']]
            buy, sell = self.mapping[order['id']]
            side = 'SELL' if order['side']=='BUY' else 'BUY'
            if side=='BUY':
                self.completed_cycles += 1
            try:
                # A partial fill does not trigger a replacement. Only total executed quantity is reused.
                oid = self.book.place(self.symbol, side, sell if side=='SELL' else buy, order['quantity'])
                self.mapping[oid] = (buy, sell)
            except ValueError as error:
                self.failures.append(str(error))  # Inventory remains marked, never silently discarded.
        return fills
