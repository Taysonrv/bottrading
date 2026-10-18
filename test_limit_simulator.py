import unittest
from limit_simulator import D, LimitBook, fixture_filters


def book(**kwargs):
    return LimitBook({'BTCUSDT': 100}, fixture_filters(), **kwargs)


class LimitSimulatorTests(unittest.TestCase):
    def test_touch_and_wrong_aggressor_do_not_fill(self):
        b = book()
        b.place('BTCUSDT', 'BUY', 95, '.25')
        self.assertEqual(b.trade(1, 'BTCUSDT', 95, 100, 'SELL'), [])
        self.assertEqual(b.trade(2, 'BTCUSDT', 94, 100, 'BUY'), [])
        self.assertEqual(b.positions['BTCUSDT'], 0)

    def test_partials_and_cancel_release_only_remaining_reserve(self):
        b = book()
        oid = b.place('BTCUSDT', 'BUY', 95, '.25')
        self.assertEqual(b.reserved_cash(), D('23.77375'))
        fills = b.trade(1, 'BTCUSDT', 94, 1, 'SELL')
        self.assertEqual(fills[0]['quantity'], D('.1'))
        self.assertEqual(b.orders[oid]['remaining'], D('.15'))
        self.assertEqual(b.cash, D('990.4905'))
        b.cancel(oid)
        self.assertEqual(b.reserved_cash(), 0)
        self.assertEqual(b.positions['BTCUSDT'], D('.1'))
        b.check_balances()

    def test_buy_sell_round_trip_accounts_for_fees(self):
        b = book()
        b.place('BTCUSDT', 'BUY', 95, '.25')
        b.trade(1, 'BTCUSDT', 94, 10, 'SELL')
        sale = b.place('BTCUSDT', 'SELL', 105, '.25')
        self.assertEqual(b.reserved_units('BTCUSDT'), D('.25'))
        b.trade(2, 'BTCUSDT', 106, 10, 'BUY')
        self.assertEqual(b.orders[sale]['status'], 'FILLED')
        self.assertEqual(b.positions['BTCUSDT'], 0)
        self.assertEqual(b.cash, D('1002.45'))
        self.assertEqual(b.fees, D('.05'))

    def test_cannot_sell_same_inventory_twice(self):
        b = book(cash=980, positions={'BTCUSDT': '.2'})
        b.place('BTCUSDT', 'SELL', 110, '.2')
        with self.assertRaises(ValueError):
            b.place('BTCUSDT', 'SELL', 120, '.2')

    def test_reservations_count_toward_symbol_budget(self):
        b = book()
        for _ in range(4):
            b.place('BTCUSDT', 'BUY', 95, '.49')
        with self.assertRaisesRegex(ValueError, 'Exposição'):
            b.place('BTCUSDT', 'BUY', 95, '.49')
        self.assertEqual(len(b.active()), 4)

    def test_volume_is_shared_across_orders_price_priority(self):
        b = book()
        low = b.place('BTCUSDT', 'BUY', 90, '.25')
        high = b.place('BTCUSDT', 'BUY', 95, '.25')
        fills = b.trade(1, 'BTCUSDT', 89, 1, 'SELL')
        self.assertEqual(sum(f['quantity'] for f in fills), D('.1'))
        self.assertEqual(fills[0]['order'], high)
        self.assertEqual(b.orders[low]['remaining'], D('.25'))

    def test_filters_and_minimum_notional(self):
        b = book()
        for price, quantity in [('95.001', '.25'), ('95', '.01'), ('95', '1'), ('NaN', '.25')]:
            with self.assertRaises(ValueError):
                b.place('BTCUSDT', 'BUY', price, quantity)
        oid = b.place('BTCUSDT', 'BUY', 95, '.2509')
        self.assertEqual(b.orders[oid]['quantity'], D('.250'))

    def test_replay_and_out_of_order_events_rejected(self):
        b = book()
        b.trade(2, 'BTCUSDT', 100, 1, 'BUY')
        for seq in (2, 1):
            with self.assertRaises(ValueError):
                b.trade(seq, 'BTCUSDT', 90, 1, 'SELL')

    def test_stop_releases_reserves_and_does_not_liquidate(self):
        stopped = False
        b = book(stop_requested=lambda: stopped)
        b.place('BTCUSDT', 'BUY', 95, '.25')
        stopped = True
        self.assertEqual(b.trade(1, 'BTCUSDT', 94, 10, 'SELL'), [])
        self.assertEqual(b.cash, 1000)
        self.assertEqual(b.reserved_cash(), 0)
        self.assertTrue(b.stopped)

    def test_drawdown_cancels_orders_but_inventory_stays_exposed(self):
        b = book(cash=800, positions={'BTCUSDT': 2})
        b.place('BTCUSDT', 'SELL', 110, '.25')
        b.trade(1, 'BTCUSDT', 20, 10, 'SELL')
        self.assertTrue(b.halted)
        self.assertEqual(b.active(), [])
        b.trade(2, 'BTCUSDT', 10, 10, 'SELL')
        self.assertEqual(b.equity(), 820)
        self.assertEqual(b.drawdown, D('.18'))
        self.assertEqual(b.positions['BTCUSDT'], 2)

    def test_reprice_requires_explicit_cancel_then_new_order(self):
        b = book()
        first = b.place('BTCUSDT', 'BUY', 95, '.25')
        b.trade(1, 'BTCUSDT', 94, 1, 'SELL')
        b.cancel(first)
        second = b.place('BTCUSDT', 'BUY', 90, '.15')
        self.assertNotEqual(first, second)
        self.assertEqual(b.orders[first]['status'], 'CANCELED')
        self.assertEqual(b.reserved_cash(), D('13.5135'))

    def test_unfunded_market_order_is_not_supported(self):
        b = book()
        with self.assertRaisesRegex(ValueError, 'passivo'):
            b.place('BTCUSDT', 'BUY', 101, '.25')

    def test_replacement_requires_a_later_event(self):
        b = book()
        b.place('BTCUSDT', 'BUY', 95, '.25')
        b.trade(1, 'BTCUSDT', 94, 10, 'SELL')
        sale = b.place('BTCUSDT', 'SELL', 105, '.25')
        self.assertEqual(b.orders[sale]['status'], 'NEW')
        self.assertEqual(len(b.fills), 1)

    def test_stop_between_two_fills_prevents_second_fill(self):
        calls = 0
        def stop():
            nonlocal calls
            calls += 1
            return calls >= 4
        b = book()
        b.place('BTCUSDT', 'BUY', 95, '.25')
        b.place('BTCUSDT', 'BUY', 90, '.25')
        b.stop_requested = stop
        fills = b.trade(1, 'BTCUSDT', 89, 10, 'SELL')
        self.assertEqual(len(fills), 1)
        self.assertTrue(b.stopped)
        self.assertEqual(b.reserved_cash(), 0)
