import unittest
from momentum_universe_research import windows


class UniverseWindowsTests(unittest.TestCase):
    def test_traded_windows_do_not_overlap(self):
        parts=windows({'SOLUSDT':list(range(780))})
        traded=[h['SOLUSDT'][60:] for h in parts]
        self.assertEqual([len(a) for a in traded],[240]*3)
        self.assertEqual(sum(traded,[]),list(range(60,780)))
    def test_short_history_rejected(self):
        with self.assertRaises(ValueError):windows({'PEPEUSDT':[1]*779})
