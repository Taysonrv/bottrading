import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from spot_engine.data import (Candle, ClosedSequence, DataError, DataGapError,
    TransientDataError, download, parse_closed_event, retry, save_history, stream_closed)

H=3_600_000


def row(t):
    return [t,100.,102.,99.,101.,10.]


def event(t,closed=True):
    return {'e':'kline','E':t+H,'s':'BTCUSDT','k':{'s':'BTCUSDT','i':'1h','t':t,'T':t+H-1,
        'x':closed,'o':'100','h':'102','l':'99','c':'101','v':'10'}}


class DataTests(unittest.TestCase):
    def client(self,pages,now=4*H):
        c=MagicMock();c.fetch_time.return_value=now;c.fetch_ohlcv.side_effect=pages
        return c

    def test_short_pages_overlap_and_closed_cutoff(self):
        c=self.client([[row(0),row(H)],[row(H),row(2*H),row(3*H),row(4*H)]],now=4*H+123)
        h=download(c,'BTC/USDT','1h',0)
        self.assertEqual([c.open_ms for c in h.candles],[0,H,2*H,3*H])
        self.assertEqual((h.pages,h.duplicates),(2,1))
        self.assertEqual(c.fetch_ohlcv.call_args_list[1].kwargs['since'],2*H)

    def test_conflicting_duplicates_rejected(self):
        bad=row(H);bad[4]=100.5
        c=self.client([[row(0),row(H)],[bad,row(2*H),row(3*H)]])
        with self.assertRaisesRegex(DataError,'conflitante'):download(c,'BTC/USDT','1h',0)

    def test_missing_first_middle_and_last_are_not_filled(self):
        for rows in ([row(H),row(2*H),row(3*H)], [row(0),row(2*H),row(3*H)], [row(0),row(H),row(2*H)]):
            with self.subTest(rows=rows),self.assertRaises(DataGapError):
                download(self.client([rows,[]]),'BTC/USDT','1h',0)

    def test_pagination_cannot_stall(self):
        with self.assertRaisesRegex(DataError,'progresso'):
            download(self.client([[row(0)],[row(0)]]),'BTC/USDT','1h',0)

    def test_unordered_and_unaligned_rows_rejected(self):
        for rows in ([row(H),row(0)], [row(1)]):
            with self.subTest(rows=rows),self.assertRaises(DataError):
                download(self.client([rows]),'BTC/USDT','1h',0)

    def test_invalid_windows_and_server_timestamps(self):
        for start,end in ((1,H),(0,H+1),(H,0),(0,5*H)):
            with self.subTest(start=start,end=end),self.assertRaises(DataError):
                download(self.client([]),'BTC/USDT','1h',start,end)
        for now in (True,float('nan'),-1):
            with self.subTest(now=now),self.assertRaises(DataError):
                download(self.client([],now),'BTC/USDT','1h',0,H)

    def test_invalid_ohlcv_cannot_become_input(self):
        for changes in ({'high':98},{'close':float('nan')},{'volume':-1},{'open':True},{'low':0}):
            values=dict(open_ms=0,open=100.,high=102.,low=99.,close=101.,volume=10.)
            values.update(changes)
            with self.subTest(changes=changes),self.assertRaises(DataError):Candle(**values)

    def test_transient_retries_bounded_and_permanent_not_retried(self):
        f=MagicMock(side_effect=[TransientDataError('temporary'),TransientDataError('temporary'),7]);sleep=MagicMock()
        self.assertEqual(retry(f,sleep),7);self.assertEqual(sleep.call_count,2)
        f=MagicMock(side_effect=TransientDataError('temporary'))
        with self.assertRaises(TransientDataError):retry(f,sleep)
        self.assertEqual(f.call_count,3)
        f=MagicMock(side_effect=DataError('permanent'))
        with self.assertRaises(DataError):retry(f,sleep)
        self.assertEqual(f.call_count,1)

    def test_unfinished_event_not_a_signal(self):
        self.assertIsNone(parse_closed_event(event(0,False),'BTC/USDT','1h',H))
        self.assertEqual(parse_closed_event(event(0),'BTC/USDT','1h',H).open_ms,0)

    def test_wrong_pair_future_stale_and_invalid_closed_flag(self):
        for change in ('pair','future','stale','flag','close_time','values'):
            m=event(0);received=H
            if change=='pair':m['k']['s']='ETHUSDT'
            if change=='future':received=H-1
            if change=='stale':received=H+120001
            if change=='flag':m['k']['x']='true'
            if change=='close_time':m['k']['T']=H
            if change=='values':m['k']['c']='NaN'
            with self.subTest(change=change),self.assertRaises(DataError):
                parse_closed_event(m,'BTC/USDT','1h',received)

    def test_sequence_deduplicates_but_requires_rest_recovery_after_gap(self):
        s=ClosedSequence('BTC/USDT','1h')
        self.assertIsNotNone(s.accept(event(0),H))
        self.assertIsNone(s.accept(event(0),H))
        with self.assertRaises(DataGapError):s.accept(event(2*H),3*H)
        self.assertEqual(s.previous.open_ms,0)
        self.assertIsNotNone(s.accept(event(H),2*H))

    def test_csv_hash_and_unique_evidence(self):
        history=download(self.client([[row(0),row(H),row(2*H),row(3*H)]]),'BTC/USDT','1h',0)
        with tempfile.TemporaryDirectory() as tmp:
            first=save_history(history,tmp);second=save_history(history,tmp)
            self.assertNotEqual(first,second)
            manifest=json.loads(first.with_suffix('.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['csv_sha256'],hashlib.sha256(first.read_bytes()).hexdigest())
            self.assertEqual(manifest['count'],4)
            self.assertFalse(manifest['approved'])
            self.assertIn('+00:00',first.read_text())

    def test_stream_bounds_checked_without_network(self):
        with patch('socket.socket',side_effect=AssertionError('network forbidden')):
            for seconds in (0,3601,True):
                with self.assertRaises(DataError):list(stream_closed('BTC/USDT','1h',seconds))

    def test_facade_is_public_spot_and_sanitizes_api_errors(self):
        import sys
        from spot_engine.data import PublicBinance
        fake=MagicMock()
        class BaseError(Exception):pass
        class RateLimitExceeded(BaseError):pass
        class NetworkError(BaseError):pass
        class ExchangeNotAvailable(NetworkError):pass
        class DDoSProtection(NetworkError):pass
        for cls in (BaseError,RateLimitExceeded,NetworkError,ExchangeNotAvailable,DDoSProtection):setattr(fake,cls.__name__,cls)
        with patch.dict(sys.modules,{'ccxt':fake}):
            c=PublicBinance();options=fake.binance.call_args.args[0]
            self.assertEqual(options['options']['fetchMarkets']['types'],['spot'])
            self.assertEqual(options['apiKey'],'');self.assertTrue(options['enableRateLimit'])
            fake.binance.return_value.fetch_time.side_effect=RateLimitExceeded('secret-url')
            with self.assertRaises(DataError) as error:c.fetch_time()
            self.assertNotIn('secret-url',str(error.exception))
            self.assertNotIsInstance(error.exception,TransientDataError)
            self.assertFalse(hasattr(c,'create_order'))
            fake.binance.return_value.fetch_time.side_effect=DDoSProtection('banned-secret')
            with self.assertRaises(DataError) as error:c.fetch_time()
            self.assertNotIsInstance(error.exception,TransientDataError)
            self.assertNotIn('banned-secret',str(error.exception))

    def fake_websocket_modules(self):
        from types import ModuleType
        client=ModuleType('websockets.sync.client');exceptions=ModuleType('websockets.exceptions')
        class WebSocketException(Exception):pass
        class ConnectionClosed(WebSocketException):pass
        exceptions.WebSocketException=WebSocketException;exceptions.ConnectionClosed=ConnectionClosed
        return client,exceptions

    def test_websocket_protocol_errors_do_not_echo_provider_response(self):
        import sys
        client,exceptions=self.fake_websocket_modules()
        client.connect=MagicMock(side_effect=exceptions.WebSocketException('secret-response'))
        with patch.dict(sys.modules,{'websockets.sync.client':client,'websockets.exceptions':exceptions}):
            with self.assertRaises(DataError) as error:list(stream_closed('BTC/USDT','1h',30))
        self.assertNotIn('secret-response',str(error.exception))
        self.assertEqual(client.connect.call_count,1)

    def test_websocket_reconnects_are_bounded(self):
        import sys
        client,exceptions=self.fake_websocket_modules()
        client.connect=MagicMock(side_effect=OSError('secret-response'))
        with patch.dict(sys.modules,{'websockets.sync.client':client,'websockets.exceptions':exceptions}),patch('spot_engine.data.time.sleep'):
            with self.assertRaisesRegex(DataError,'Reconexões'):list(stream_closed('BTC/USDT','1h',30))
        self.assertEqual(client.connect.call_count,4)

    def test_websocket_gap_aborts_without_reconnecting(self):
        import sys
        client,exceptions=self.fake_websocket_modules()
        ws=MagicMock();ws.recv.return_value=json.dumps(event(2*H))
        client.connect=MagicMock();client.connect.return_value.__enter__.return_value=ws
        with patch.dict(sys.modules,{'websockets.sync.client':client,'websockets.exceptions':exceptions}),patch('spot_engine.data.time.time',return_value=3*H/1000):
            with self.assertRaises(DataGapError):list(stream_closed('BTC/USDT','1h',30,previous=Candle(*row(0))))
        self.assertEqual(client.connect.call_count,1)
