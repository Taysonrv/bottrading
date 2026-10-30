from unittest import TestCase
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path
from session_performance import coverage,load
from spot_engine.main import save


class SessionPerformanceTests(TestCase):
    def test_unobserved_prefix_suffix_and_sampling_gap_remain_unknown(self):
        c=coverage(dict(start_ms=100000,end_ms=300000),dict(started=120,updated=180,recent_seconds=30,stopped_seconds=10,unknown_seconds=20),250000)
        self.assertEqual(c['elapsed_seconds'],150)
        self.assertEqual(c['unknown_seconds'],110)
        self.assertEqual(c['sampled_recent_fraction'],.2)

    def test_inconsistent_or_future_sampling_does_not_create_uptime(self):
        for h in (dict(started=100,updated=200,recent_seconds=1000,stopped_seconds=0,unknown_seconds=0),dict(started=100,updated=9999,recent_seconds=1,stopped_seconds=0,unknown_seconds=0)):
            self.assertEqual(coverage(dict(start_ms=100000,end_ms=300000),h,200000)['unknown_seconds'],100)

    def test_monitor_start_before_wallet_is_clipped_conservatively(self):
        c=coverage(dict(start_ms=100000,end_ms=300000),dict(started=98,updated=200,recent_seconds=90,stopped_seconds=0,unknown_seconds=12),200000)
        self.assertEqual(c['recent_seconds'],88)
        self.assertEqual(c['unknown_seconds'],12)

    def test_ledger_result_includes_fees_and_does_not_invent_sharpe(self):
        with TemporaryDirectory() as tmp:
            folder=Path(tmp)/'reports/local/portfolio';folder.mkdir(parents=True)
            save(folder/'plan.json',dict(start_ms=100,end_ms=200000))
            s=dict(fills=[dict(side='BUY',quantity='1',price='10',fee='.01'),dict(side='SELL',quantity='1',price='11',fee='.011')],
                cash='20.979',realized='.979',fees='.021',position=None,pending=None,halt=None)
            with patch('session_performance.ledger',return_value=s):r=load(tmp,100000)
            self.assertEqual(r['equity'],'20.979');self.assertEqual(r['unrealized_net'],'0.000')
            self.assertEqual(r['closed_cycles'],1);self.assertIsNone(r['sharpe']);self.assertIsNone(r['profit_factor'])
            self.assertFalse(r['approved'])

    def test_open_position_without_matching_recent_mark_is_unknown(self):
        with TemporaryDirectory() as tmp:
            s=dict(fills=[],cash='14',realized='0',fees='0',position={'quantity':'1'},pending=None,halt=None)
            with patch('session_performance.ledger',return_value=s):r=load(tmp,100000)
            self.assertIsNone(r['equity']);self.assertIsNone(r['net_return'])
