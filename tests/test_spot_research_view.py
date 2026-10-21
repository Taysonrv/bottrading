import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import spot_research_view


class ResearchViewTests(unittest.TestCase):
    def test_nested_universe_report_is_loaded_without_duplicates(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            folder=root/'reports/local/spot-universe/batch/reports'
            folder.mkdir(parents=True)
            row=dict(start_ms=0,end_ms=1000,net_return=-.1,buy_hold_return=.2,
                     max_drawdown=.1,closed_trades=1,win_rate=0,profit_factor=0,sharpe_zero_rf=-1)
            report=dict(scope='CHRONOLOGICAL_EXPLORATORY_AUDIT',approved=False,
                        symbol='BTC/USDT',timeframe='15m',scenarios=[dict(name='base',windows=[row])])
            path=folder/'BTC-USDT.json'
            path.write_text(json.dumps(report),encoding='utf-8')
            with patch.object(spot_research_view,'__file__',str(root/'spot_research_view.py')):
                actual=spot_research_view.load(root)
                self.assertEqual(len(actual['reports']),1)
                self.assertEqual(actual['reports'][0]['rows'][0]['net_return'],-.1)
                self.assertFalse(actual['approved'])
                report['approved']=True
                path.write_text(json.dumps(report),encoding='utf-8')
                rejected=spot_research_view.load(root)
                self.assertFalse(rejected['available'])
                self.assertEqual(rejected['invalid'],1)

    def test_missing_is_not_zero_return(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with patch.object(spot_research_view,'__file__',str(root/'spot_research_view.py')):
                result=spot_research_view.load(root)
            self.assertFalse(result['available'])
            self.assertEqual(result['reports'],[])

class JournalTests(unittest.TestCase):
    def test_journal_integrity_reconciliation_and_bounded_rows(self):
        import hashlib
        from spot_research_view import trade_journal
        with tempfile.TemporaryDirectory() as temp:
            batch=Path(temp); reports=batch/'reports';reports.mkdir()
            report=reports/'BTC-USDT.json'
            header='mode,cost_scenario,exit_reason,window,entry_candle_open_ms,exit_candle_open_ms,quantity,entry,exit_price,gross_pnl,slippage_cost,fees,net_pnl\n'
            row='fixed,base,STOP,1,1000,2000,1,100,99,-1,.1,.1,-1.2\n'
            raw=(header+row*35).encode()
            path=batch/'BTC-USDT-trades.csv';path.write_bytes(raw)
            digest=hashlib.sha256(raw).hexdigest()
            result=trade_journal(report,digest)
            self.assertTrue(result['available'])
            self.assertEqual(result['groups'][0]['count'],35)
            self.assertEqual(len(result['groups'][0]['trades']),30)
            self.assertAlmostEqual(result['groups'][0]['net'],-42)
            path.write_bytes(raw+b'corrupt')
            self.assertFalse(trade_journal(report,digest)['available'])
            broken=(header+row.replace('-1.2','99')).encode()
            path.write_bytes(broken)
            self.assertFalse(trade_journal(report,hashlib.sha256(broken).hexdigest())['available'])
