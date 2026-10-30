from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock,patch
from prospective_protocol import register,registration,collect,view,verify_all,HOUR,folder
from spot_engine.data import Candle,History
from donchian_strategy import signals
from spot_engine.config import load_settings
from tests.test_single_exit_research import hours


def history(start,end,observed):
    rows=tuple(Candle(t,100,101,99,100,10) for t in range(start,end,HOUR))
    return History('BTC/USDT','1h',start,end,observed,rows,1,0)


class ProspectiveProtocolTests(TestCase):
    def register(self,tmp):return register(tmp,1000*HOUR+123)

    def test_registration_future_aligned_fixed_and_exclusive(self):
        with TemporaryDirectory() as tmp:
            r=self.register(tmp)
            self.assertEqual(r['start_ms'],1001*HOUR)
            self.assertEqual(r['end_ms']-r['start_ms'],30*24*HOUR)
            self.assertFalse(r['execution_authorized']);self.assertFalse(r['external_notarization'])
            self.assertEqual(verify_all(tmp)['batches'],0)
            with self.assertRaises(FileExistsError):self.register(tmp)

    def test_tampered_registration_or_code_is_refused(self):
        with TemporaryDirectory() as tmp:
            r=self.register(tmp)
            with patch('prospective_protocol.fingerprint',return_value={'changed':'code'}):
                with self.assertRaisesRegex(ValueError,'PROTOCOL_CODE_CHANGED'):registration(tmp)
            p=folder(tmp)/'registration.json';p.write_text(p.read_text().replace('BTC/USDT','ETH/USDT'))
            with self.assertRaisesRegex(ValueError,'REGISTRATION_HASH_MISMATCH'):registration(tmp)

    def test_registration_near_hour_boundary_keeps_five_minute_margin(self):
        with TemporaryDirectory() as tmp:
            now=1000*HOUR+59*60000;r=register(tmp,now)
            self.assertEqual(r['start_ms'],1002*HOUR)
            self.assertGreater(r['start_ms']-now,300000)

    def test_malformed_state_does_not_break_readonly_view(self):
        with TemporaryDirectory() as tmp:
            self.register(tmp);(folder(tmp)/'state.json').write_text('[]')
            self.assertEqual(view(tmp)['status'],'PROTOCOL_INTEGRITY_ERROR')

    def test_no_data_download_before_first_future_close(self):
        with TemporaryDirectory() as tmp:
            r=self.register(tmp);client=Mock();client.fetch_time.return_value=r['start_ms']+1
            with patch('prospective_protocol.download') as fetch:
                out=collect(tmp,client)
            fetch.assert_not_called();self.assertEqual(out['future_bars'],0)
            self.assertEqual(out['status'],'WAITING_FIRST_FUTURE_CLOSE')

    def test_snapshot_idempotent_warmup_excluded_and_tampering_detected(self):
        with TemporaryDirectory() as tmp:
            r=self.register(tmp);client=Mock();client.fetch_time.return_value=r['start_ms']+HOUR+1
            with patch('prospective_protocol.download',side_effect=lambda c,s,t,start,end:history(start,end,client.fetch_time.return_value)) as fetch:
                first=collect(tmp,client);second=collect(tmp,client)
            self.assertEqual(fetch.call_count,1);self.assertEqual(first['future_bars'],1)
            self.assertEqual(first['last_sha256'],second['last_sha256'])
            self.assertEqual(verify_all(tmp)['future_bars'],1)
            self.assertTrue(view(tmp)['local_hashes_match'])
            p=next((folder(tmp)/'data').glob('*.json'));p.write_text(p.read_text()+' ')
            self.assertEqual(view(tmp)['status'],'PROTOCOL_INTEGRITY_ERROR')

    def test_past_candle_revision_does_not_replace_old_batch(self):
        with TemporaryDirectory() as tmp:
            r=self.register(tmp);client=Mock();client.fetch_time.return_value=r['start_ms']+HOUR+1
            def fetch(c,s,t,start,end):return history(start,end,client.fetch_time.return_value)
            with patch('prospective_protocol.download',side_effect=fetch):first=collect(tmp,client)
            client.fetch_time.return_value+=HOUR
            def revised(c,s,t,start,end):
                h=fetch(c,s,t,start,end);rows=list(h.candles);rows[0]=replace(rows[0],close=100.5)
                return replace(h,candles=tuple(rows))
            with patch('prospective_protocol.download',side_effect=revised):
                with self.assertRaisesRegex(ValueError,'PAST_CANDLE_REVISION'):collect(tmp,client)
            self.assertEqual(len(list((folder(tmp)/'data').glob('*.json'))),1)

    def test_no_orders_or_wallet_and_closed_window_is_data_only(self):
        with TemporaryDirectory() as tmp:
            r=self.register(tmp);client=Mock();client.fetch_time.return_value=r['end_ms']+HOUR
            with patch('prospective_protocol.download',side_effect=lambda c,s,t,start,end:history(start,end,client.fetch_time.return_value)):
                out=collect(tmp,client)
            self.assertEqual(out['future_bars'],720)
            self.assertEqual(out['status'],'WINDOW_CLOSED_DATA_ONLY')
            self.assertFalse(out['validated']);self.assertEqual(out['orders'],0)
            self.assertFalse((Path(tmp)/'reports/local/portfolio').exists())

    def test_breakout_uses_previous_twenty_highs_not_current_or_future(self):
        cfg=load_settings({});h=hours(21);bars=list(h.candles)
        bars[20]=replace(bars[20],open=100,high=200,low=99,close=102);h=replace(h,candles=tuple(bars))
        from spot_engine.strategy import analyze
        proto=replace(analyze(hours(),cfg)[-1],ready=True,ema_trend=100,atr_fraction=.01)
        with patch('donchian_strategy.analyze',return_value=(proto,)*21):
            self.assertEqual(signals(h,cfg)[20].action,'ENTER_LONG')
        with patch('donchian_strategy.analyze',return_value=(replace(proto,atr_fraction=.03),)*21):
            self.assertEqual(signals(h,cfg)[20].action,'HOLD')

    def test_strategy_is_causal_and_not_an_order_adapter(self):
        h=hours(650);cfg=load_settings({})
        prefix=replace(h,candles=h.candles[:620],end_ms=620*HOUR)
        self.assertEqual(signals(prefix,cfg),signals(h,cfg)[:620])
