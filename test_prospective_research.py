import unittest
from prospective_research import create_plan,HOUR


class FutureResearchTests(unittest.TestCase):
    def test_cutoff_always_strictly_in_future(self):
        for now in (0,3600,3600.5):
            p=create_plan({},now,'code')
            self.assertGreater(p['cutoff'],now*1000)
            self.assertEqual(p['cutoff']%HOUR,0)

    def test_hypotheses_fixed_and_not_approved(self):
        p=create_plan({'BTCUSDT':{}},1,'code')
        self.assertEqual(p['entry_intervals'],[1,24])
        self.assertEqual(p['capital'],20)
        self.assertFalse(p['approved'])
