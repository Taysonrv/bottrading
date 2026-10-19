import time
import unittest
from paper_lab import cycle,daily_signal,CONFIG


class PaperLabTests(unittest.TestCase):
    def state(self):
        return dict(cash=1000.,positions={},peak=1000.,halted=False,last={})

    def signals(self,target=1):
        return {s:dict(candle='day1',target=target) for s in CONFIG['symbols']}

    def quotes(self):
        return {s:dict(bid=100.,ask=100.1) for s in CONFIG['symbols']}

    def test_paper_buys_and_duplicate_daily_candle_cannot_buy_again(self):
        state = self.state()
        orders=cycle(state,self.signals(),self.quotes())
        self.assertEqual(len(orders),2)
        self.assertGreaterEqual(state['cash'],900)
        self.assertEqual(cycle(state,self.signals(),self.quotes()),[])
        self.assertEqual(state['accounting']['orders'],2)

    def test_zero_signal_keeps_cash_without_forced_trades(self):
        state=self.state()
        self.assertEqual(cycle(state,self.signals(0),self.quotes()),[])
        self.assertEqual(state['performance']['equity'],1000)

    def test_stop_immediately_before_fill_prevents_order(self):
        state=self.state()
        calls=0
        def stop():
            nonlocal calls
            calls+=1
            return calls>=2
        self.assertEqual(cycle(state,self.signals(),self.quotes(),stop),[])
        self.assertEqual(state['cash'],1000)

    def test_drawdown_latches(self):
        state=self.state()
        state.update(cash=800.,positions={'BTCUSDT':2.},peak=1200.)
        self.assertEqual(cycle(state,self.signals(),self.quotes()),[])
        self.assertTrue(state['halted'])
        quotes=self.quotes()
        quotes['BTCUSDT']=dict(bid=700.,ask=700.1)
        self.assertEqual(cycle(state,self.signals(),quotes),[])

    def test_daily_signal_ignores_open_day_and_rejects_gap(self):
        now=int(time.time())//86400*86400+100
        rows=[[int(now//86400*86400-86400*(210-i))*1000,0,0,0,100+i,0,
               int(now//86400*86400-86400*(209-i))*1000-1] for i in range(211)]
        first=daily_signal(rows,now)
        rows[-1][4]=1
        self.assertEqual(daily_signal(rows,now),first)
        del rows[30]
        with self.assertRaises(ValueError):
            daily_signal(rows,now)
