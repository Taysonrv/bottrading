import unittest
import accounting
import research


class AccountingTests(unittest.TestCase):
    def state(self):
        return {'cash': 1000., 'positions': {}, 'peak': 1000., 'halted': False}

    def trade(self, state, side, price, value):
        previous = state['positions'].get('BTCUSDT', 0.)
        state['cash'], state['positions']['BTCUSDT'], order = research.fill(
            state['cash'], previous, price, value if side == 'BUY' else -value, .001, .001)
        if order:
            accounting.record(state, 'BTCUSDT', previous, order)
        return order

    def test_buy_then_partial_sale_reconciles(self):
        state = self.state()
        accounting.initialize(state, {})
        self.trade(state, 'BUY', 100, 200)
        self.trade(state, 'SELL', 120, 100)
        result = accounting.mark(state, {'BTCUSDT': 120}, .001, .001)
        self.assertGreater(result['realized_pnl'], 0)
        self.assertGreater(result['unrealized_pnl'], 0)
        self.assertAlmostEqual(result['total_pnl'], result['realized_pnl'] + result['unrealized_pnl'])

    def test_complete_roundtrip_has_no_unrealized_pnl(self):
        state = self.state()
        accounting.initialize(state, {})
        self.trade(state, 'BUY', 100, 200)
        self.trade(state, 'SELL', 100, state['positions']['BTCUSDT'] * 100)
        result = accounting.mark(state, {'BTCUSDT': 100}, .001, .001)
        self.assertAlmostEqual(result['unrealized_pnl'], 0)
        self.assertLess(result['realized_pnl'], 0)
        self.assertEqual(result['losing_sales'], 1)
        self.assertEqual(result['orders'], 2)

    def test_existing_holdings_use_activation_bid_and_preserve_risk(self):
        state = {'cash': 100., 'positions': {'BTCUSDT': 2.}, 'peak': 500., 'halted': True}
        accounting.initialize(state, {'BTCUSDT': 100})
        result = accounting.mark(state, {'BTCUSDT': 100}, .001, .001)
        self.assertEqual(result['initial_equity'], 300)
        self.assertEqual(state['peak'], 500)
        self.assertTrue(state['halted'])
        self.assertLess(result['total_pnl'], 0)  # Estimated closing costs.

    def test_reinitialization_never_resets_losses(self):
        state = self.state()
        accounting.initialize(state, {})
        self.trade(state, 'BUY', 100, 200)
        self.trade(state, 'SELL', 50, state['positions']['BTCUSDT'] * 50)
        loss = state['accounting']['realized_pnl']
        accounting.initialize(state, {'BTCUSDT': 500})
        self.assertEqual(state['accounting']['realized_pnl'], loss)
        self.assertEqual(state['accounting']['initial_equity'], 1000)

    def test_external_wallet_change_is_detected(self):
        state = self.state()
        accounting.initialize(state, {})
        state['cash'] += 50
        with self.assertRaises(ValueError):
            accounting.mark(state, {}, .001, .001)


if __name__ == '__main__':
    unittest.main()
