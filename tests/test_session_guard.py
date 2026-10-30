from unittest import TestCase
from session_guard import decision
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
from spot_engine.main import save
from session_guard import cycle


class GuardTests(TestCase):
    def check(self,**changes):
        args=dict(plan=dict(start_ms=100,end_ms=200000),status=dict(updated_ms=100000,phase='RUNNING'),
            control=dict(updated_ms=100000,phase='RUNNING'),now_ms=100010,stop=False,port_open=False,attempts=0)
        args.update(changes);return decision(**args)

    def test_healthy_supervisor_prevents_duplicate_panel(self):
        self.assertEqual(self.check(),'SUPERVISOR_HANDLES_RECOVERY')

    def test_stale_supervisor_can_restore_only_panel(self):
        self.assertEqual(self.check(control={}), 'RESTORE_PANEL_ONLY')
        self.assertEqual(self.check(control={},status={},port_open=True),'ENGINE_REQUIRES_REVIEW')

    def test_stop_deadline_and_invalid_plan_block_recovery(self):
        self.assertEqual(self.check(stop=True),'STOP')
        self.assertEqual(self.check(now_ms=200000),'DEADLINE')
        self.assertEqual(self.check(plan={}), 'INVALID_PLAN')

    def test_retry_limit_and_clock_rollback(self):
        self.assertEqual(self.check(control={},attempts=3,status={}), 'ENGINE_REQUIRES_REVIEW')
        self.assertEqual(self.check(now_ms=99999),'CLOCK_UNVERIFIED')

    def test_missing_ui_recovers_after_grace_even_if_supervisor_is_alive(self):
        self.assertEqual(self.check(panel_missing_ms=120000),'RESTORE_PANEL_ONLY')
        self.assertEqual(self.check(panel_missing_ms=119999),'SUPERVISOR_HANDLES_RECOVERY')
        self.assertNotEqual(self.check(panel_missing_ms=120000,attempts=3),'RESTORE_PANEL_ONLY')

    def test_explicit_ui_refresh_does_not_bypass_stop_or_deadline(self):
        self.assertEqual(self.check(planned_refresh=True),'RESTORE_PANEL_ONLY')
        self.assertEqual(self.check(planned_refresh=True,stop=True),'STOP')
        self.assertEqual(self.check(planned_refresh=True,now_ms=200000),'DEADLINE')

    def test_planned_panel_refresh_preserves_access_without_logging_it(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'reports/local';(folder/'portfolio').mkdir(parents=True)
            save(folder/'portfolio/plan.json',dict(start_ms=100,end_ms=2000000))
            save(folder/'portfolio/status.json',dict(updated_ms=1000000,phase='RUNNING'))
            save(folder/'system-run.json',dict(updated_ms=1000000,phase='RUNNING'))
            save(folder/'panel-refresh.json',dict(requested_ms=1000000,access_code='test-secret-123456'))
            with patch('session_guard.time.time',return_value=1000),patch('session_guard.listening',return_value=False),patch('session_guard.subprocess.Popen') as spawn:
                spawn.return_value.pid=123;r=cycle(root,8769)
            self.assertEqual(r['state'],'RESTORE_PANEL_ONLY')
            self.assertEqual(spawn.call_args.kwargs['env']['SPOTLAB_ACCESS_CODE'],'test-secret-123456')
            self.assertNotIn('test-secret',str(r))
            self.assertNotIn('test-secret',(folder/'supervisor-events.jsonl').read_text())
