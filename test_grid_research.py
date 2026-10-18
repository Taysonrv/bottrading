import copy
import unittest
import grid_research as grid
import research


CONFIG = dict(max_symbol_fraction=.2, max_order_fraction=.05, max_total_fraction=.6,
              fee_rate=.001, slippage_rate=.001)


def candles(count=300):
    return [dict(open_time=i*research.HOUR, time=(i+1)*research.HOUR-1,
                 open=100., high=120., low=80., close=100.) for i in range(count)]


class GridResearchTests(unittest.TestCase):
    def test_lower_level_increases_target_and_rebound_reduces_it(self):
        rows = candles()
        rows[200]['close'] = 90
        targets, _ = grid.schedule(rows, CONFIG)
        # Large daily decline invokes the crash filter; use slower movements below instead.
        self.assertEqual(targets[201], 0.)
        rows = candles()
        rows[200]['close'] = 95
        targets, _ = grid.schedule(rows, CONFIG)
        self.assertEqual(targets[201], .625)
        self.assertEqual(targets[202], .5)

    def test_future_changes_cannot_change_prior_decisions(self):
        rows = candles()
        changed = copy.deepcopy(rows)
        changed[220].update(open=50., high=51., low=49., close=50.)
        for hybrid in (False, True):
            before, _ = grid.schedule(rows, CONFIG, hybrid)
            after, _ = grid.schedule(changed, CONFIG, hybrid)
            self.assertEqual(before[:221], after[:221])

    def test_break_closes_episode_and_enforces_cooldown(self):
        rows = candles()
        rows[200].update(open=70., high=71., low=69., close=70.)
        target, metadata = grid.schedule(rows, CONFIG)
        self.assertEqual(target[201:225], [0.]*24)
        self.assertGreater(metadata['breaks'], 0)

    def test_range_does_not_move_during_episode(self):
        rows = candles()
        rows[201]['high'] = 130
        _, metadata = grid.schedule(rows, CONFIG)
        bands = metadata['bands']
        self.assertTrue(all(r['upper'] == 120. and r['lower'] == 80. for r in bands))

    def test_costs_can_veto_too_narrow_grid(self):
        rows = candles()
        for row in rows:
            row.update(high=100.1, low=99.9)
        target, metadata = grid.schedule(rows, CONFIG)
        self.assertFalse(any(target))
        self.assertEqual(metadata['episodes'], 0)

    def test_total_equity_counts_inventory_losses(self):
        rows = candles()
        for i in range(210, len(rows)):
            rows[i].update(open=50., high=51., low=49., close=50.)
        schedule, _ = grid.schedule(rows, CONFIG)
        r = research.backtest({'BTCUSDT': rows}, 200, len(rows), CONFIG, 'grid', None,
                             target_at=lambda s, i: schedule[i])
        self.assertLess(r['return'], 0)
        self.assertGreater(r['drawdown'], 0)
        self.assertFalse(r['passed'])

    def test_stop_prevents_all_orders(self):
        rows = candles()
        target, _ = grid.schedule(rows, CONFIG)
        r = research.backtest({'BTCUSDT': rows}, 200, len(rows), CONFIG, 'grid', None,
                             target_at=lambda s, i: target[i], stop_requested=lambda: True)
        self.assertEqual(r['trades'], 0)
        self.assertTrue(r['manually_stopped'])
