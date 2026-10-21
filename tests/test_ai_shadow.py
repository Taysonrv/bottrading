import json
import tempfile
from pathlib import Path
import unittest
from ai_shadow.contracts import decision
from ai_shadow.state import snapshot
from ai_shadow.journal import Journal
from ai_shadow.risk import assess
from ai_shadow.policy import judge
from ai_shadow.jev_client import FixtureClient
from ai_shadow.calibration import label, brier, baseline
from ai_shadow.review import review


def response(**overrides):
    r=dict(regime='trending',direction='long',probabilities={'long':.94,'short':.03,'neutral':.03},confidence=.91,
           toxic_flow=False,setup_quality=2.5,risk_state='safe',model='fixture-v1',schema='shadow-v1')
    r.update(overrides);return r


def book(**overrides):
    r=dict(symbol='BTCUSDT',bid=100,ask=100.01,bid_qty=3,ask_qty=1,received_at=4000,event_at=3999,sequence=5,continuous=True)
    r.update(overrides);return r


def account(**overrides):
    r=dict(equity=20,cash=20,positions=0,inventory_fraction=0)
    r.update(overrides);return r


def history():return [{'time':4000-(60-i)*60,'received_at':4000-(60-i)*60,'close':100+i*.001} for i in range(61)]


class ContractTests(unittest.TestCase):
    def test_score_not_rounded(self):self.assertEqual(decision(response(setup_quality=1.99))['setup_quality'],1.99)
    def test_nan_boolean_and_extra_rejected(self):
        for change in ({'setup_quality':float('nan')},{'setup_quality':True},{'execute':True},{'toxic_flow':None}):
            with self.assertRaises(ValueError):decision(response(**change))
    def test_probability_and_confidence_consistency(self):
        for change in ({'confidence':.99},{'probabilities':{'long':.5,'short':.5,'neutral':.5}},{'direction':'short'}):
            with self.assertRaises(ValueError):decision(response(**change))


class StateTests(unittest.TestCase):
    def test_extreme_finite_inputs_cannot_create_infinity(self):
        s=snapshot(book(bid=1e308,ask=1e308,bid_qty=1e308,ask_qty=1e308),history(),account(),4000)
        import math
        self.assertTrue(all(math.isfinite(s[k]) for k in ('mid','spread','imbalance_l1','volatility')))
    def test_numeric_features(self):
        s=snapshot(book(),history(),account(),4000)
        self.assertAlmostEqual(s['mid'],100.005);self.assertAlmostEqual(s['imbalance_l1'],.5)
        self.assertFalse(s['token_count_verified'])
    def test_future_stale_missing_and_gap_rejected(self):
        for change in ({'received_at':4001},{'received_at':3990},{'bid_qty':None},{'continuous':False},{'event_at':4001}):
            with self.assertRaises(ValueError):snapshot(book(**change),history(),account(),4000)
        h=history();del h[20]
        with self.assertRaises(ValueError):snapshot(book(),h,account(),4000)
    def test_delayed_historical_event_rejected(self):
        h=history();h[10]['received_at']=4001
        with self.assertRaises(ValueError):snapshot(book(),h,account(),4000)
    def test_last_received_event_must_be_causal(self):
        h=history();h[-1]['time']=4001
        with self.assertRaises(ValueError):snapshot(book(),h,account(),4000)


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'journal.sqlite'
        self.j=Journal(self.path,'plan-1','code-1')
    def tearDown(self):self.j.close();self.tmp.cleanup()
    def test_idempotency_and_budget_unknown_after_restart(self):
        self.assertTrue(self.j.reserve('a',{'x':1},0))
        self.assertFalse(self.j.reserve('a',{'x':1},0))
        self.j.close();self.j=Journal(self.path,'plan-1','code-1')
        self.assertEqual(self.j.request('a')['phase'],'unknown')
        self.assertEqual(self.j.request('a')['reserved_cost'],0)
        self.assertFalse(self.j.reserve('a',{'x':1},0))
    def test_changed_plan_cannot_reuse_session(self):
        with self.assertRaises(ValueError):Journal(self.path,'plan-2','code-1')
    def test_empty_checkpoint_cannot_reset_latched_risk(self):
        assess(self.j,account(),4000)
        self.j.put('risk',{})
        with self.assertRaises(ValueError):assess(self.j,account(),4001)
    def test_partial_or_nonfinite_checkpoint_is_rejected(self):
        assess(self.j,account(),4000)
        original=self.j.get('risk')
        for change in ({'peak':0},{'day_start':0},{'halted':'false'},{'last_at':5000},{'day':-1}):
            self.j.put('risk',{**original,**change})
            with self.assertRaises(ValueError):assess(self.j,account(),4001)
    def test_missing_risk_checkpoint_is_not_reset(self):
        assess(self.j,account(),4000)
        with self.j.db:self.j.db.execute("DELETE FROM kv WHERE key='risk'")
        with self.assertRaises(ValueError):assess(self.j,account(),4001)
    def test_duplicate_id_with_changed_snapshot_is_error(self):
        self.j.reserve('a',{'x':1},0)
        with self.assertRaises(ValueError):self.j.reserve('a',{'x':2},0)
    def test_review_requirement_persists(self):
        risk=assess(self.j,account(),4000)
        self.assertEqual(judge(response(regime='crisis'),risk,journal=self.j)['action'],'REVIEW_REQUIRED')
        risk=assess(self.j,account(),4001)
        self.assertEqual(judge(response(),risk,journal=self.j)['action'],'HOLD')
    def test_inconsistent_inventory_is_blocked(self):
        with self.assertRaises(ValueError):assess(self.j,account(cash=15),4000)
    def test_second_writer_refused(self):
        with self.assertRaises(ValueError):Journal(self.path,'plan-1','code-1')
    def test_paid_cost_always_rejected_in_offline_session(self):
        with self.assertRaises(ValueError):self.j.reserve('a',{},.01)
    def test_nonboolean_eligibility_cannot_approve_candidate(self):
        self.assertEqual(judge(response(),{'eligible':'false'})['action'],'HOLD')
    def test_changed_plan_rejected_after_writer_closed(self):
        self.j.close()
        with self.assertRaises(ValueError):Journal(self.path,'plan-2','code-1')
        self.j=Journal(self.path,'plan-1','code-1')
    def test_stop_and_local_risk_override_safe(self):
        risk=assess(self.j,account(),4000,stop=True)
        self.assertEqual(judge(response(),risk)['action'],'HOLD')
    def test_drawdown_latches_after_recovery(self):
        assess(self.j,account(),4000)
        self.assertFalse(assess(self.j,account(equity=17,cash=17),4001)['eligible'])
        self.assertFalse(assess(self.j,account(equity=21,cash=21),4002)['eligible'])
    def test_daily_loss_survives_restart_and_recovery(self):
        assess(self.j,account(),4000);assess(self.j,account(equity=19.3,cash=19.3),4001)
        self.j.close();self.j=Journal(self.path,'plan-1','code-1')
        self.assertFalse(assess(self.j,account(),4002)['eligible'])
        self.assertTrue(assess(self.j,account(),90000)['eligible'])
    def test_backdated_risk_cannot_reset_day(self):
        assess(self.j,account(),90000)
        with self.assertRaises(ValueError):assess(self.j,account(),4000)
    def test_short_low_quality_and_kelly_blocked(self):
        risk=assess(self.j,account(),4000)
        self.assertEqual(judge(response(direction='short',probabilities={'long':.03,'short':.94,'neutral':.03}),risk)['action'],'HOLD')
        self.assertEqual(judge(response(setup_quality=1.99),risk)['action'],'HOLD')
        self.assertFalse(judge(response(),risk)['kelly_enabled'])
        self.assertFalse(judge(response(),risk)['trading_enabled'])
    def test_existing_position_blocks_candidate(self):
        self.assertFalse(assess(self.j,account(positions=1,inventory_fraction=.25,cash=15),4000)['eligible'])
    def test_fixture_client_never_accepts_live_request(self):
        with self.assertRaises(ValueError):FixtureClient().evaluate({})
        with self.assertRaises(TimeoutError):FixtureClient(response(),latency=3).evaluate({})


class CalibrationTests(unittest.TestCase):
    def test_extreme_price_ratio_keeps_net_return_finite(self):
        r=label(dict(predicted_at=100,probability=.8),dict(time=101,received_at=101,ask=1.797e308),dict(time=3701,received_at=3701,bid=1.797e308),3702)
        self.assertAlmostEqual(r['net_return'],.999*.999/(1.001*1.001)-1)
    def test_brier_rejects_nonfinite_timestamps(self):
        with self.assertRaises(ValueError):brier([dict(probability=.8,outcome=1,label_at=float('nan'),predicted_at=100)])
    def test_only_future_quote_matures_label(self):
        prediction=dict(predicted_at=100,probability=.8)
        entry=dict(time=101,received_at=101,ask=100)
        exit=dict(time=3701,received_at=3701,bid=101)
        self.assertIsNone(label(prediction,entry,exit,3700))
        result=label(prediction,entry,exit,3702)
        self.assertEqual(result['outcome'],1)
        self.assertAlmostEqual(brier([result]),.04)
    def test_missing_or_late_outcome_not_imputed(self):
        p=dict(predicted_at=100,probability=.8);entry=dict(time=101,received_at=101,ask=100)
        self.assertIsNone(label(p,entry,None,5000))
        self.assertIsNone(label(p,entry,dict(time=3800,received_at=3800,bid=101),5000))
    def test_baseline_uses_only_development_outcomes(self):
        rows=[dict(outcome=1,label_at=100),dict(outcome=0,label_at=300)]
        self.assertEqual(baseline(rows,200),1)
    def test_review_cannot_activate_schema(self):
        r=review([]);self.assertFalse(r['auto_apply']);self.assertFalse(r['approved'])
        self.assertIsNone(r['brier']);self.assertNotIn('pnl',r)


class RunnerTests(unittest.TestCase):
    def test_offline_smoke_and_deduplication(self):
        from ai_shadow_run import run
        with tempfile.TemporaryDirectory() as tmp:
            r=run(Path(tmp))
            self.assertEqual(r['orders'],0);self.assertEqual(r['requests_paid'],0)
            self.assertTrue(r['synthetic_response']);self.assertEqual(r['mode'],'OFFLINE_FIXTURE')
            self.assertTrue(run(Path(tmp))['duplicate'])
    def test_stop_in_offline_demo_is_hold(self):
        from ai_shadow_run import run
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run(Path(tmp),stop=True)['decision']['action'],'HOLD')


class ReplayTests(unittest.TestCase):
    def test_replay_preserves_inputs_and_refuses_reordered_sequence(self):
        from ai_shadow.collector import ReplayCollector
        c=ReplayCollector();b=book();c.accept(b)
        b['bid']=1
        self.assertEqual(c.latest(4000)['bid'],100)
        with self.assertRaises(ValueError):c.accept(book(sequence=4))
    def test_replay_never_reads_after_cutoff(self):
        from ai_shadow.collector import ReplayCollector
        c=ReplayCollector();c.accept(book())
        with self.assertRaises(ValueError):c.latest(3999)
    def test_circuit_survives_restart_without_network(self):
        from ai_shadow.jev_client import CircuitBreaker
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'j.sqlite';j=Journal(path,'p','c');c=CircuitBreaker(j)
            for at in (100,101,102):c.failure(at)
            self.assertFalse(c.allowed(103));j.close()
            j=Journal(path,'p','c');c=CircuitBreaker(j)
            self.assertFalse(c.allowed(120));self.assertTrue(c.allowed(162))
            c.success(162);self.assertTrue(c.allowed(163));j.close()
