from dataclasses import replace
from decimal import Decimal as D
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from spot_engine.data import Candle,History
from spot_engine.risk import Rules
from single_exit_research import Policy,hourly,proposal,run


def rules(minimum='5'):
    return Rules('BTC/USDT',1700000000000,D('.001'),D('.001'),D(10000),D('.01'),D('.01'),D(1000000),D(minimum),D(10000000))


def hours(n=605,change=None):
    cs=[]
    for i in range(n):
        o,h,l,c=(100.,100.1,99.9,100.)
        if change: o,h,l,c=change(i,o,h,l,c)
        cs.append(Candle(i*3600000,o,h,l,c,10))
    return History('BTC/USDT','1h',0,n*3600000,n*3600000,tuple(cs),0,0)


def signals(history,cfg):
    return tuple(SimpleNamespace(action='ENTER_LONG' if i==600 else 'HOLD') for i in range(len(history.candles)))


class SingleExitTests(unittest.TestCase):
    def test_complete_utc_aggregation_and_source_gap(self):
        bars=tuple(Candle(i*900000,100,101,99,100,10) for i in range(1,10))
        h=History('BTC/USDT','15m',900000,10*900000,10*900000,bars,0,0)
        result=hourly(h)
        self.assertEqual(len(result.candles),1);self.assertEqual(result.candles[0].open_ms,3600000)
        self.assertEqual(result.candles[0].volume,40)
        with self.assertRaisesRegex(ValueError,'GAP'):
            hourly(replace(h,candles=bars[:3]+bars[4:]))

    def test_single_exit_six_usdt_fits_minimum_and_risk(self):
        p=proposal(rules(),D(20),D(20),D(100),D('.6'))
        self.assertEqual(p['reason'],'HYPOTHETICAL_PLAN')
        self.assertLessEqual(D(p['cost']),D(6));self.assertGreater(D(p['cost']),D(5))
        self.assertLessEqual(D(p['estimated_stop_loss']),D('.2'))
        self.assertGreaterEqual(D(p['net_rr']),D('1.5'));self.assertFalse(p['execution_authorized'])
        self.assertNotEqual(proposal(rules('10'),D(20),D(20),D(100),D('.6'))['reason'],'HYPOTHETICAL_PLAN')

    def test_budget_not_rounded_up_and_zero_remaining_rejects(self):
        p=proposal(rules(),D(20),D(20),D(100),D(0))
        self.assertNotEqual(p['reason'],'HYPOTHETICAL_PLAN')
        p=proposal(rules(),D(20),D(20),D(100),D('.05'))
        self.assertNotEqual(p['reason'],'HYPOTHETICAL_PLAN')

    def test_next_open_and_stop_before_target(self):
        def change(i,o,h,l,c):
            return (110,120,100,110) if i==601 else (o,h,l,c)
        with patch('single_exit_research.analyze',signals):r=run(hours(change=change),rules())
        self.assertEqual(r['closed_trades'],1);t=r['trades'][0]
        self.assertEqual(t['entry_ms'],601*3600000);self.assertGreater(D(t['entry']),D(110))
        self.assertEqual(t['reason'],'STOP');self.assertLess(D(t['pnl']),0)
        self.assertEqual(D(r['cash']),D(20)+D(t['pnl']))
        self.assertFalse(r['approved'])

    def test_full_exit_only_and_no_opposite_ema_exit(self):
        with patch('single_exit_research.analyze',lambda h,c:tuple(SimpleNamespace(action='ENTER_LONG' if i==600 else 'EXIT_LONG') for i in range(len(h.candles)))):
            r=run(hours(660),rules())
        self.assertEqual(r['closed_trades'],1);self.assertEqual(r['trades'][0]['reason'],'TIME_STOP')
        self.assertEqual(r['trades'][0]['exit_ms']-r['trades'][0]['entry_ms'],48*3600000)
        self.assertEqual(D(r['cash']),D(20)+D(r['net_realized']))

    def test_gap_below_exchange_minimum_retains_inventory(self):
        def change(i,o,h,l,c):return (50,50.1,49.9,50) if i>=602 else (o,h,l,c)
        with patch('single_exit_research.analyze',signals):r=run(hours(change=change),rules())
        self.assertTrue(r['position_open']);self.assertEqual(r['closed_trades'],0)
        self.assertGreater(r['blocked_exit_attempts'],0)

    def test_causal_prefix_and_fixed_parameters(self):
        with self.assertRaises(ValueError):Policy(target=D('.08'))
        with self.assertRaises(ValueError):Policy(capital=20.0)
        h=hours()
        with patch('single_exit_research.analyze',signals):
            a=run(h,rules());b=run(hours(610),rules())
        # Both explicit final-liquidation trades have the same entry and qty;
        # later bars cannot change an already chosen size or entry price.
        self.assertEqual(a['trades'][0]['entry'],b['trades'][0]['entry'])
        self.assertEqual(a['trades'][0]['quantity'],b['trades'][0]['quantity'])


if __name__=='__main__':unittest.main()
