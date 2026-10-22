import tempfile
import unittest
from unittest.mock import patch
from operation_health import sample


def health(fresh=True,phase='RUNNING'):
    return dict(execution=dict(fresh=fresh,phase=phase,reason='TEST',age_seconds=1),market=dict(fresh=fresh,age_seconds=1))


class AvailabilityTests(unittest.TestCase):
    def test_first_sample_and_restart_do_not_invent_past_uptime(self):
        with tempfile.TemporaryDirectory() as tmp,patch('operation_health.build',return_value=health()):
            self.assertEqual(sample(tmp,1000)['recent_seconds'],0)
            s=sample(tmp,1015);self.assertEqual(s['recent_seconds'],15)
            s=sample(tmp,2000);self.assertEqual(s['recent_seconds'],15)
            self.assertEqual(s['unknown_seconds'],985);self.assertEqual(s['last_gap_seconds'],985)

    def test_stop_and_transition_are_separate_from_unknown_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('operation_health.build',return_value=health()):sample(tmp,1000)
            with patch('operation_health.build',return_value=health(False,'STOPPED')):
                sample(tmp,1015);s=sample(tmp,1030)
            self.assertEqual(s['stopped_seconds'],15);self.assertEqual(s['unknown_seconds'],15)
            self.assertEqual(len(s['transitions']),2)

    def test_clock_reversal_refused(self):
        with tempfile.TemporaryDirectory() as tmp,patch('operation_health.build',return_value=health()):
            sample(tmp,1000)
            with self.assertRaises(ValueError):sample(tmp,999)
