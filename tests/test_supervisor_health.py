import json
from pathlib import Path
import tempfile
import unittest
from supervisor_health import Recovery, event, previous_run


class SupervisorHealthTests(unittest.TestCase):
    def test_engine_never_restarts(self):
        r=Recovery()
        for t in (0,100,999999):
            self.assertFalse(r.ready('execution',t))

    def test_backoff_is_bounded_and_independent(self):
        r=Recovery()
        self.assertFalse(r.ready('dashboard',0))
        self.assertFalse(r.ready('dashboard',14))
        self.assertTrue(r.ready('dashboard',15));r.attempted('dashboard',15)
        self.assertFalse(r.ready('dashboard',44))
        self.assertTrue(r.ready('dashboard',45));r.attempted('dashboard',45)
        self.assertFalse(r.ready('dashboard',104))
        self.assertTrue(r.ready('dashboard',105));r.attempted('dashboard',105)
        self.assertFalse(r.ready('dashboard',10000))
        self.assertFalse(r.ready('market',10000))
        self.assertTrue(r.ready('market',10015))
        self.assertFalse(r.ready('dashboard',float('nan')))

    def test_previous_gap_does_not_claim_a_cause_or_include_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'reports/local';folder.mkdir(parents=True)
            (folder/'system-run.json').write_text(json.dumps(dict(phase='RUNNING',updated_ms=1000)))
            previous_run(tmp,now=100)
            event(tmp,'TEST',reason='TEST',password='SECRET',command='SECRET')
            rows=(folder/'supervisor-events.jsonl').read_text().splitlines()
            first=json.loads(rows[0]);self.assertEqual(first['reason'],'CAUSE_UNKNOWN')
            self.assertEqual(first['age_seconds'],99)
            self.assertNotIn('SECRET',''.join(rows))
            self.assertFalse((folder/'portfolio').exists())

    def test_clean_shutdown_not_reported_as_abrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'reports/local';folder.mkdir(parents=True)
            (folder/'system-run.json').write_text(json.dumps(dict(phase='STOPPED',updated_ms=1000)))
            previous_run(tmp,now=100)
            self.assertFalse((folder/'supervisor-events.jsonl').exists())
