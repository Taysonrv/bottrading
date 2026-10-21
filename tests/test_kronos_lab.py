import unittest
from spot_engine.kronos_lab import quantile,summarize,score

H=3600000


class KronosLabTests(unittest.TestCase):
    def test_paths_are_separate_and_quantiles_known(self):
        paths=[[90,100],[110,120]]
        summary=summarize(paths,2)
        self.assertEqual(summary[0],dict(step=1,p10=92,p50=100,p90=108))
        self.assertEqual(paths,[[90,100],[110,120]])

    def test_invalid_paths_fail_closed(self):
        for paths in ([],[[100,float('nan')]],[[100,0]],[[True,100]],[[100]],[[100,float('inf')]]):
            with self.assertRaises(ValueError):summarize(paths,2)

    def report(self):
        return dict(scope='KRONOS_OBSERVE_ONLY',orders=0,cutoff_ms=H,issued_ms=H+1000,
                    anchor_close=100,bands=[dict(p10=90,p50=100,p90=110),dict(p10=100,p50=110,p90=120)])

    def test_unclosed_future_is_not_scored(self):
        result=score(self.report(),[105,115],2*H+1000)
        self.assertEqual(result['evaluated_steps'],1)
        self.assertEqual(result['status'],'PARTIAL')
        self.assertEqual(result['median_mae'],5)
        self.assertEqual(result['flat_price_mae'],5)

    def test_pending_is_not_zero_error(self):
        result=score(self.report(),[],H+2000)
        self.assertEqual(result['status'],'PENDING')
        self.assertNotIn('median_mae',result)
        self.assertFalse(result['approved'])

    def test_no_false_approval_even_when_coverage_perfect(self):
        result=score(self.report(),[100,110],3*H)
        self.assertEqual(result['model_band_coverage'],1)
        self.assertEqual(result['median_mae'],0)
        self.assertEqual(result['flat_price_mae'],5)
        self.assertFalse(result['approved'])

    def test_observation_time_cannot_precede_issue(self):
        with self.assertRaises(ValueError):score(self.report(),[100],H)
