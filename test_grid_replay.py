import copy
import unittest
from grid_controller import GridEpisode
from grid_replay import replay, validate_tape, symbol_filters, download_period
from limit_simulator import LimitBook, fixture_filters


def tape(prices):
    return [dict(a=i+1, T=1000+i, p=str(p), q='10', m=(i%2==1)) for i, p in enumerate(prices)]


class GridReplayTests(unittest.TestCase):
    def test_diagnostics_distinguish_unreached_levels(self):
        r = replay(tape([100,99.9,100.1]),fixture_filters())
        self.assertEqual(r['diagnostics']['events_below_initial_first_buy'],0)
        self.assertIn('não atravessou',r['diagnostics']['explanation'])

    def test_diagnostics_distinguish_insufficient_execution_volume(self):
        rows = tape([100,99,99.1])
        for row in rows:
            row['q'] = '.000001'
        r = replay(rows,fixture_filters())
        self.assertEqual(r['summary']['fills'],0)
        self.assertGreater(r['diagnostics']['aggressive_sell_events_below_initial_first_buy'],0)
        self.assertIn('não houve fill',r['diagnostics']['explanation'])

    def test_full_order_journal_keeps_cancellation_and_remaining(self):
        r = replay(tape([100,99,100.1]),fixture_filters())
        self.assertTrue(any(o['status']=='FILLED' for o in r['orders']))
        self.assertTrue(any(o['status']=='CANCELED' for o in r['orders']))
        self.assertEqual(r['net_liquidation_estimate'],r['summary']['equity'])
    def test_pagination_keeps_events_with_same_millisecond(self):
        from urllib.parse import urlparse, parse_qs
        first = [dict(a=i, T=100, p='100', q='1', m=True) for i in range(1,1001)]
        second = [dict(a=1001,T=100,p='100',q='1',m=True),
                  dict(a=1002,T=200,p='100',q='1',m=True)]
        calls = []
        def get(path):
            calls.append(parse_qs(urlparse(path).query))
            return first if len(calls)==1 else second
        rows = download_period(get,'BTCUSDT',100,200)
        self.assertEqual(len(rows),1001)
        self.assertEqual(calls[1]['fromId'], ['1001'])
        self.assertNotIn('startTime',calls[1])

    def test_incomplete_or_capped_download_fails(self):
        rows = tape([100,99])
        with self.assertRaisesRegex(ValueError, 'Limite de páginas'):
            download_period(lambda path: rows, 'BTCUSDT',0,2000,max_pages=1)
        pages = iter([rows,[]])
        with self.assertRaisesRegex(ValueError,'incompletos'):
            download_period(lambda path: next(pages), 'BTCUSDT',0,2000)

    def test_gap_between_pages_is_rejected(self):
        pages = iter([tape([100,99]), [dict(a=4,T=2000,p='100',q='1',m=True)]])
        with self.assertRaisesRegex(ValueError,'lacuna'):
            download_period(lambda path:next(pages),'BTCUSDT',0,2000)

    def test_buy_sell_then_replacement_without_same_event_reuse(self):
        result = replay(tape([100, 99, 100.1]), fixture_filters())
        self.assertEqual(result['completed_cycles'], 1)
        self.assertEqual(len(result['fills']), 2)
        self.assertEqual(result['fills'][0]['sequence'], 2)
        self.assertEqual(result['fills'][1]['sequence'], 3)
        self.assertEqual(result['active_at_cutoff'], 4)
        self.assertEqual(result['summary']['active_orders'], 0)
        self.assertFalse(result['approved_for_trading'])

    def test_partial_buy_does_not_create_sell_until_complete(self):
        b = LimitBook({'BTCUSDT':100}, fixture_filters())
        e = GridEpisode(b, 'BTCUSDT', levels=1)
        e.advance(1, 99, 1, 'SELL')
        self.assertEqual([o['side'] for o in b.active()], ['BUY'])
        e.advance(2, 99, 10, 'SELL')
        self.assertEqual([o['side'] for o in b.active()], ['SELL'])

    def test_break_cancels_without_losing_inventory(self):
        b = LimitBook({'BTCUSDT':100}, fixture_filters())
        e = GridEpisode(b, 'BTCUSDT', levels=1)
        e.advance(1, 99, 10, 'SELL')
        units = b.positions['BTCUSDT']
        e.advance(2, 90, 10, 'SELL')
        self.assertTrue(e.closed)
        self.assertEqual(b.active(), [])
        self.assertEqual(b.positions['BTCUSDT'], units)

    def test_duplicate_gap_or_backwards_time_rejected(self):
        for field, value in [('a',1), ('a',3), ('T',0), ('m','true')]:
            rows = tape([100,99])
            rows[1][field] = value
            with self.assertRaises(ValueError):
                validate_tape(rows)

    def test_future_price_does_not_change_anchor_or_past_fills(self):
        rows = tape([100,99,100.1,100])
        changed = copy.deepcopy(rows)
        changed[-1]['p'] = '90'
        first = replay(rows, fixture_filters())
        second = replay(changed, fixture_filters())
        self.assertEqual(first['anchor'], second['anchor'])
        self.assertEqual(first['fills'], second['fills'])

    def test_stop_prevents_episode_orders(self):
        r = replay(tape([100,99,100.1]), fixture_filters(), stop_requested=lambda: True)
        self.assertEqual(r['summary']['fills'], 0)
        self.assertTrue(r['summary']['stopped'])

    def test_market_filters_extract_stricter_minimum(self):
        info = {'symbols':[dict(symbol='BTCUSDT', status='TRADING', filters=[
            dict(filterType='PRICE_FILTER',tickSize='.01',minPrice='.01',maxPrice='1000000'),
            dict(filterType='LOT_SIZE',stepSize='.001',minQty='.001',maxQty='100'),
            dict(filterType='MIN_NOTIONAL',minNotional='5'),
            dict(filterType='NOTIONAL',minNotional='10')])]}
        self.assertEqual(symbol_filters(info,'BTCUSDT')['BTCUSDT']['min_notional'],'10')
