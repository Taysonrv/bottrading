import copy
from decimal import Decimal as D
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from spot_engine.data import Candle, History
from spot_engine.validation import bootstrap,phase1,rolling
from spot_engine.config import load_settings
from v3_engine.collector import ParallelCollector,CollectionError
from v3_engine.shadow_bridge import shadow_observe,build_shadow_input
from v3_engine.position import open_position,advance
from v3_engine.risk_state import assess
from v3_engine.live import Observer
from v3_engine.atr_protection import levels
from v3_engine.selection import choose
import v3_view


class V3ServiceTests(unittest.TestCase):
    def test_bootstrap_reproducible_empty_and_loss(self):
        a=bootstrap([{'pnl':1},{'pnl':-2}],20,42)
        self.assertEqual(a,bootstrap([{'pnl':1},{'pnl':-2}],20,42))
        self.assertFalse(bootstrap([],20,42)['robust'])
        self.assertFalse(bootstrap([{'pnl':-2}],20,42)['robust'])
        self.assertFalse(phase1(dict(net_return=1,closed_trades=29,win_rate=.9,profit_factor=4,max_drawdown=.01,sharpe_zero_rf=2),{'robust':True}))

    def test_rolling_training_precedes_test_and_overlap_is_explicit(self):
        cs=tuple(Candle(i*900000,100,101,99,100,10) for i in range(25000))
        h=History('BTC/USDT','15m',0,len(cs)*900000,len(cs)*900000,cs,1,0)
        parts=list(rolling(h,load_settings({})))
        self.assertEqual(len(parts),1)
        bounds,part=parts[0]
        self.assertEqual(bounds['train_end_ms'],bounds['test_start_ms'])
        self.assertEqual(len(part.candles),600+5840)
        self.assertLess(part.start_ms,bounds['test_start_ms'])

    def test_parallel_errors_and_client_thread_isolation(self):
        class Client:
            def fetch_book(self,s):
                if s=='BAD':raise ValueError('secret provider detail')
                return {'symbol':s}
        with ParallelCollector(['GOOD','BAD'],client_factory=lambda timeout:Client()) as c:
            r=c.fetch_books(.5)
            self.assertEqual(r['GOOD'],{'symbol':'GOOD'})
            self.assertIsInstance(r['BAD'],CollectionError)
            self.assertNotIn('secret',str(r['BAD']))
        with self.assertRaises(ValueError):ParallelCollector(['X'],max_workers=7)

    def test_timeout_does_not_spawn_replacement_worker(self):
        gate=threading.Event();calls=[]
        class Client:
            def fetch_book(self,s):calls.append(s);gate.wait(2);return s
        c=ParallelCollector(['ONE'],client_factory=lambda timeout:Client())
        try:
            start=time.monotonic();r=c.fetch_books(.03)
            self.assertLess(time.monotonic()-start,.5);self.assertIsInstance(r['ONE'],Exception)
            r=c.fetch_books(.03);self.assertIn('PREVIOUS_REQUEST',str(r['ONE']))
            self.assertEqual(calls,['ONE'])
        finally:gate.set();c.close()

    def test_shadow_unverified_and_contract_clamp(self):
        s=dict(score=100,regime='TREND',action='ENTER',symbol='BTC/USDT')
        original=copy.deepcopy(s);inputs=build_shadow_input(s,{})
        self.assertEqual(inputs['raw']['setup_quality'],3)
        r=shadow_observe(s,{})
        self.assertFalse(r['concordance']);self.assertFalse(r['execution_authorized'])
        self.assertEqual(r['shadow_judgment']['reason'],'UNVERIFIED_ACCOUNT_AND_FLOW')
        self.assertEqual(s,original)
        with patch('v3_engine.shadow_bridge.judge',side_effect=ValueError('secret')):
            self.assertEqual(shadow_observe(s,{})['status'],'SHADOW_UNAVAILABLE')

    def test_risk_latches_reset_daily_not_drawdown(self):
        r=assess(None,equity=D(100),now_ms=0)
        r=assess(r['state'],equity=D(89),now_ms=1)
        self.assertEqual(r['reason'],'DRAWDOWN')
        r=assess(r['state'],equity=D(100),now_ms=86400000)
        self.assertTrue(r['state']['drawdown_halted']);self.assertFalse(r['state']['daily_halted'])
        r=assess(None,equity=D(100),now_ms=0)
        for i in range(4):r=assess(r['state'],equity=D(100),now_ms=i+1,closed_trade_pnl=D(-1))
        self.assertEqual(r['reason'],'FOUR_LOSSES')
        self.assertEqual(assess(r['state'],equity=D(100),now_ms=9,stopped=True)['reason'],'STOP')

    def plan(self):
        return dict(valid_research_plan=True,execution_authorized=False,symbol='BTC/USDT',quantity='10',
            estimated_cost='1001',entry='100',stop='98.2',exits=[
            dict(quantity='4',target='102'),dict(quantity='3.5',target='103.5'),dict(quantity='2.5',target='105')])

    def test_stop_before_tp_and_no_retroactive_trailing(self):
        p=open_position(self.plan(),0);before=copy.deepcopy(p)
        c=Candle(0,100,106,97,101,100)
        q,events=advance(p,c,as_of_ms=900000,atr=D(1),tick=D('.01'))
        self.assertEqual(events[0]['reason'],'STOP');self.assertTrue(q['closed']);self.assertEqual(p,before)
        c=Candle(0,100,103,99,102,100)
        q,events=advance(p,c,as_of_ms=900000,atr=D(1),tick=D('.01'))
        self.assertEqual([e['reason'] for e in events],['TP1']);self.assertGreater(D(q['stop']),D(p['stop']))
        self.assertFalse(q['closed']);self.assertEqual(q['remaining'],'6')

    def test_partial_quantity_conservation_and_time_stop(self):
        p=open_position(self.plan(),0)
        q,events=advance(p,Candle(0,100,106,99,105,100),as_of_ms=900000,atr=D(1),tick=D('.01'))
        self.assertEqual(sum(D(e['quantity']) for e in events),D(10));self.assertTrue(q['closed'])
        p=open_position(self.plan(),0)
        for i in range(32):p,events=advance(p,Candle(i*900000,100,100.1,99.9,100,100),
                as_of_ms=(i+1)*900000,atr=D(1),tick=D('.01'))
        self.assertTrue(p['closed']);self.assertEqual(events[0]['reason'],'TIME_STOP')

    def test_view_does_not_fallback_to_offline_or_invent_equity(self):
        with tempfile.TemporaryDirectory() as root:
            v=v3_view.load(root,1000);self.assertFalse(v['available']);self.assertFalse(v['fresh'])
            self.assertIsNone(v['agreement_recent'])

    def test_observer_stop_no_network_no_wallet(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root,'STOP').touch();o=Observer(root,['BTC/USDT'])
            r=o.cycle(None,1000)
            self.assertEqual(r['reason'],'STOP');self.assertFalse(r['execution_authorized'])
            self.assertIsNone(r['equity']);self.assertFalse(Path(root,'reports/local/portfolio').exists())

    def test_atr_level_and_rr_contradiction(self):
        r=levels(D(50000),D(100),D('.01'))
        self.assertEqual(D(r['stop']),D(49820));self.assertEqual(D(r['take']),D(50200))
        self.assertLess(D(r['gross_rr']),D('1.5'));self.assertFalse(r['execution_authorized'])

    def test_optional_priority_never_uses_unknown_regime(self):
        rows=[dict(symbol='BTC/USDT',eligible=True,spread_fraction='.001',regime_v3={'detected':'UNKNOWN'}),
              dict(symbol='ETH/USDT',eligible=True,spread_fraction='.002',regime_v3={'detected':'TREND'})]
        self.assertEqual(choose(rows),'BTC/USDT');self.assertEqual(choose(rows,True),'ETH/USDT')

    def test_observer_coverage_excludes_bootstrap_and_gaps(self):
        class Context:
            def state(self):return dict(decision_ms=900000,ready=True,regime='TRANSITION')
        class Collector:
            timings={}
            def fetch_books(self):return {'BTC/USDT':dict(symbol='BTCUSDT',bidPrice='100',askPrice='100.01',bidQty='1',askQty='1')}
        from v3_engine.strategies import Signal
        with tempfile.TemporaryDirectory() as root:
            o=Observer(root,['BTC/USDT']);o.cutoff=900000;o.contexts['BTC/USDT']=Context()
            with patch('v3_engine.live.evaluate',return_value=Signal('OBSERVE','TEST','TRANSITION',0,{})):
                with patch('v3_engine.live.time.monotonic',side_effect=[0,0,0,20,20]):
                    o.cycle(Collector(),900000)
                self.assertEqual(o.coverage,0);self.assertEqual(o.previous_ok,920000)
                o.cycle(Collector(),935000);self.assertGreaterEqual(o.coverage,15)
                covered=o.coverage;o.cycle(Collector(),1000000);self.assertEqual(o.coverage,covered)


if __name__=='__main__':unittest.main()
