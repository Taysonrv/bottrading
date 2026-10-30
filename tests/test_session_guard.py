from unittest import TestCase
from session_guard import decision


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
