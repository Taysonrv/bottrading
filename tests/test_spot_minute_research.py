from decimal import Decimal as D
import unittest
from spot_engine.data import Candle
from spot_engine.risk import Rules
from spot_engine.minute_research import Breakout,Intent,simulate,M


class MinuteTests(unittest.TestCase):
    def bars(self,n=2251):
        return tuple(Candle(i*M,100+i*.01,100+i*.01+.002,100+i*.01-.002,100+i*.01,10 if i==2250 else 1) for i in range(n))

    def test_warmup_and_prior_volume_breakout(self):
        strategy=Breakout();results=[strategy.update(c) for c in self.bars()]
        self.assertTrue(all(not r.enter for r in results[:2249]))
        self.assertFalse(results[2249].enter)
        self.assertTrue(results[2250].enter)
        self.assertEqual(results[2250].stop_fraction,.003)

    def test_future_prefix_invariance(self):
        a=Breakout();b=Breakout();bars=self.bars()
        first=[a.update(c) for c in bars]
        prefix=[b.update(c) for c in bars[:2200]]
        self.assertEqual(first[:2200],prefix)

    def test_unfinished_15m_block_cannot_update_trend(self):
        s=Breakout()
        for c in self.bars(15):s.update(c)
        self.assertEqual(s.bars15,1)
        previous=s.slow
        s.update(Candle(15*M,200,201,199,200,1))
        self.assertEqual(s.bars15,1)
        self.assertEqual(s.slow,previous)

    def test_gap_rejected_before_state_mutation(self):
        s=Breakout();s.update(self.bars(1)[0])
        with self.assertRaises(ValueError):s.update(self.bars(3)[2])
        self.assertEqual(s.last.open_ms,0)

    def test_stop_first_and_next_open_price(self):
        rules=Rules('BTC/USDT',0,D('.001'),D('.001'),D('100'),D('.01'),D('.01'),D('10000'),D('5'),D('10000'))
        bars=(Candle(0,100,100,100,100,1),Candle(M,100,110,90,100,1))
        intents=(Intent(True,'TEST',.01),Intent(False,'TEST'))
        result=simulate(bars,intents,1,2,rules)
        self.assertEqual(result['closed_trades'],1)
        self.assertLess(result['net_return'],0)
        flat=(bars[0],Candle(M,200,200,200,200,1))
        result=simulate(flat,intents,1,2,rules,fee=0,slip=0)
        self.assertAlmostEqual(result['net_return'],0)

    def test_minimum_notional_cannot_force_oversized_buy(self):
        rules=Rules('BTC/USDT',0,D('.001'),D('.001'),D('100'),D('.01'),D('.01'),D('10000'),D('10'),D('10000'))
        bars=(Candle(0,100,100,100,100,1),Candle(M,100,101,99,100,1))
        result=simulate(bars,(Intent(True,'TEST',.01),Intent(False,'TEST')),1,2,rules)
        self.assertEqual(result['closed_trades'],0)
        self.assertEqual(result['net_return'],0)
        self.assertEqual(result['blocked'],1)
