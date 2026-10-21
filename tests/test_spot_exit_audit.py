from decimal import Decimal as D
import unittest
from spot_engine.data import Candle
from spot_engine.risk import Rules
from spot_engine.minute_research import simulate,Intent

H=3600000


class ExitAuditTests(unittest.TestCase):
    def setUp(self):
        self.rules=Rules('BTC/USDT',0,D('.001'),D('.001'),D('100'),D('.01'),D('.01'),D('10000'),D('5'),D('10000'))
        self.intents=[Intent(True,'TEST',.02)]+[Intent(False,'NO_SIGNAL')]*5

    def test_net_reconciles_gross_slippage_and_fees(self):
        bars=(Candle(0,100,101,99,100,1),Candle(H,100,110,99,105,1))
        r=simulate(bars,self.intents,1,2,self.rules,step_ms=H,journal=True)
        t=r['trade_journal'][0]
        self.assertAlmostEqual(t['net_pnl'],t['gross_pnl']-t['slippage_cost']-t['fees'])
        self.assertAlmostEqual(r['net_return']*20,t['net_pnl'])
        self.assertEqual(t['entry_candle_open_ms'],t['signal_close_ms'])

    def test_trailing_only_effective_after_close_and_monotonic(self):
        bars=(Candle(0,100,101,99,100,1),Candle(H,100,112,99,110,1),
              Candle(2*H,110,112,106,111,1),Candle(3*H,111,113,109,110,1))
        r=simulate(bars,self.intents,1,4,self.rules,step_ms=H,journal=True,
                   exit_mode='trailing',atrs=[1]*4)
        # Low99 in the first trading bar cannot trigger a stop computed at its close107.
        self.assertEqual(r['trade_journal'][0]['exit_candle_open_ms'],2*H)
        self.assertTrue(all(t['new']>t['old'] for t in r['stop_changes']))
        self.assertEqual(r['stop_changes'][0]['effective_from_ms'],2*H)
        self.assertEqual(r['trade_journal'][0]['exit_reason'],'STOP')

    def test_gap_exit_uses_open_below_stop(self):
        bars=(Candle(0,100,101,99,100,1),Candle(H,100,101,99,100,1),Candle(2*H,90,91,89,90,1))
        r=simulate(bars,self.intents,1,3,self.rules,step_ms=H,journal=True)
        self.assertEqual(r['trade_journal'][0]['exit_reason'],'STOP_GAP')
        self.assertEqual(r['trade_journal'][0]['exit_reference'],90)

    def test_invalid_exit_mode_rejected(self):
        with self.assertRaises(ValueError):simulate((),(),1,2,self.rules,exit_mode='unknown')
