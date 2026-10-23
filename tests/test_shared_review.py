import json
from pathlib import Path
import tempfile
import unittest
from session_audit import shared_review
from spot_engine.portfolio import Portfolio


class SharedReviewTests(unittest.TestCase):
    def test_missing_data_is_unknown_and_never_creates_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);r=shared_review(root,now=100)
            self.assertIsNone(r['wallet']);self.assertFalse(r['approved'])
            self.assertIsNone(r['session_expired'])
            self.assertFalse(r['live_enabled']);self.assertEqual(list(root.iterdir()),[])

    def test_full_ledger_cash_is_known_without_market_quote(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);Portfolio(root).initialize(1000)
            before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            r=shared_review(root,now=100)
            self.assertEqual(r['wallet']['equity'],'20');self.assertEqual(r['wallet']['total_pnl'],'0')
            self.assertEqual(r['wallet']['orders'],0);self.assertEqual(r['wallet']['buy_fills'],0)
            self.assertIn('Sem preenchimentos', ' '.join(r['issues']))
            after={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(before,after)

    def test_monitor_gaps_and_telegram_staleness_are_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'reports/local';folder.mkdir(parents=True)
            (folder/'operation-health.json').write_text(json.dumps(dict(started=1,updated=99,recent_seconds=10,stopped_seconds=0,unknown_seconds=88)))
            (folder/'portfolio').mkdir()
            (folder/'portfolio/alerts-status.json').write_text(json.dumps(dict(updated_ms=1000,telegram_enabled=True)))
            r=shared_review(tmp,now=1000)
            self.assertEqual(r['availability']['unknown_seconds'],88)
            self.assertIsNone(r['telegram_enabled']);self.assertFalse(r['approved'])
            self.assertIn('continuidade não demonstrada',' '.join(r['issues']))

    def test_invalid_review_clock_rejected(self):
        for clock in (float('nan'),float('inf'),-1,True):
            with self.assertRaises(ValueError):shared_review('.',now=clock)
