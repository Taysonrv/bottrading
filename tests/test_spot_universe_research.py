from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import json
from spot_engine.universe_research import research_one


class UniverseTests(unittest.TestCase):
    def test_same_interval_and_frozen_policy_no_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            csv=folder/'sample.csv';csv.write_text('fixture')
            history=SimpleNamespace(candles=(1,2,3))
            report=dict(approved=False,caveats=[],scenarios=[dict(name='base',positive_windows=0,
                        beat_buy_hold_windows=0,windows=[dict(net_return=-.01)])])
            with patch('spot_engine.universe_research.download',return_value=history) as download, patch('spot_engine.universe_research.save_history',return_value=csv), patch('spot_engine.universe_research.evaluate',return_value=report) as evaluate:
                result=research_one(object(),'SOL/USDT',1000,2000,folder)
            self.assertEqual(download.call_args.args[1:],('SOL/USDT','15m',1000,2000))
            self.assertEqual(str(evaluate.call_args.args[1].max_order_notional),'6')
            self.assertEqual(evaluate.call_args.args[2],4)
            self.assertEqual(result['status'],'COMPLETE')
            stored=json.loads((folder/'reports/SOL-USDT.json').read_text(encoding='utf-8'))
            self.assertFalse(stored['approved'])
            self.assertIn('backtest.py',stored['source_hashes'])
