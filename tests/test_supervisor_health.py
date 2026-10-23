import json
from pathlib import Path
import tempfile
import unittest
from supervisor_health import Recovery, event, previous_run, persist_status
from unittest.mock import Mock


class SupervisorHealthTests(unittest.TestCase):
    def test_windows_status_sharing_error_retried_without_engine_side_effect(self):
        writer=Mock(side_effect=[PermissionError('sharing'),PermissionError('sharing'),None]);sleep=Mock()
        self.assertTrue(persist_status(Path('status.json'),{'phase':'RUNNING'},writer,sleep))
        self.assertEqual(writer.call_count,3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list],[.05,.1])

    def test_persistent_heartbeat_io_error_returns_unavailable(self):
        writer=Mock(side_effect=PermissionError('sharing'));sleep=Mock()
        self.assertFalse(persist_status(Path('status.json'),{},writer,sleep))
        self.assertEqual(writer.call_count,3)
        disk=Mock(side_effect=OSError('disk'))
        self.assertFalse(persist_status(Path('status.json'),{},disk,sleep))
        self.assertEqual(disk.call_count,1)

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
