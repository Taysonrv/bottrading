import unittest
import diagnostics


class DiagnosticsTests(unittest.TestCase):
    def assess(self, **changes):
        values = dict(config_ok=True, stop=False, halted=False, validation_exists=True,
                      validation_current=True, validation_passed=True, observation_exists=False,
                      observation_current=False, activity_recent=False, performance_exists=False)
        values.update(changes)
        return diagnostics.assess(**values)

    def test_failed_validation_blocks_orders_but_not_observation(self):
        report = self.assess(validation_passed=False)
        self.assertFalse(report['paper_ready'])
        self.assertTrue(report['observation_ready'])

    def test_stop_blocks_both_modes(self):
        report = self.assess(stop=True)
        self.assertFalse(report['paper_ready'])
        self.assertFalse(report['observation_ready'])

    def test_expired_approval_does_not_appear_ready(self):
        self.assertFalse(self.assess(validation_current=False)['paper_ready'])

    def test_old_session_requires_archival(self):
        report = self.assess(observation_exists=True, observation_current=False)
        self.assertFalse(report['observation_ready'])
        row = next(c for c in report['checks'] if c['code'] == 'observation')
        self.assertEqual(row['status'], 'blocked')

    def test_risk_halt_blocks_orders_without_erasing_state(self):
        report = self.assess(halted=True)
        self.assertFalse(report['paper_ready'])
        self.assertTrue(report['observation_ready'])

    def test_invalid_config_blocks_both_modes(self):
        report = self.assess(config_ok=False)
        self.assertFalse(report['paper_ready'])
        self.assertFalse(report['observation_ready'])

    def test_missing_heartbeat_is_not_mistaken_for_activity(self):
        row = next(c for c in self.assess()['checks'] if c['code'] == 'activity')
        self.assertEqual(row['status'], 'attention')


if __name__ == '__main__':
    unittest.main()
