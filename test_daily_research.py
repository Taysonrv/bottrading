import copy
import unittest
import daily_research as daily


def candles(count=220):
    return [dict(open_time=i*daily.DAY, time=(i+1)*daily.DAY-1,
                 open=100+i, high=101+i, low=99+i, close=100+i) for i in range(count)]


class DailyResearchTests(unittest.TestCase):
    def test_future_bars_do_not_change_prior_signals(self):
        rows = candles()
        changed = copy.deepcopy(rows)
        changed[210]['close'] = 1
        for rule in daily.RULES:
            for scaled in (False, True):
                self.assertEqual(daily.targets(rows, rule, scaled)[:211],
                                 daily.targets(changed, rule, scaled)[:211])

    def test_breakout_uses_high_and_low_and_remembers_position(self):
        rows = candles()
        rows[199]['close'] = 302
        rows[200]['close'] = 300
        rows[201]['close'] = 1
        signals = daily.targets(rows, 'breakout55_20', False)
        self.assertEqual(signals[200:203], [1., 1., 0.])

    def test_volatility_never_leverages(self):
        for rule in daily.RULES:
            self.assertTrue(all(0 <= v <= 1 for v in daily.targets(candles(), rule, True)))

    def test_downtrend_is_cash(self):
        rows = candles()
        for i, row in enumerate(rows):
            row['close'] = 1000-i
        self.assertEqual(daily.targets(rows, 'sma200', False)[200:], [0.]*20)
        self.assertEqual(daily.targets(rows, 'momentum90', False)[200:], [0.]*20)

    def test_partial_daily_history_rejected(self):
        with self.assertRaises(ValueError):
            daily.evaluate({'BTCUSDT': candles()}, {})

    def test_daily_download_paginates_and_excludes_open_day(self):
        rows = candles(2025)
        def request(url):
            import urllib.parse
            query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            self.assertEqual(query['interval'], ['1d'])
            start = int(query['startTime'][0]) // daily.DAY
            return [[r['open_time'], r['open'], r['high'], r['low'], r['close'], 0, r['time']]
                    for r in rows[start:start+1000]]
        self.assertEqual(daily.download('BTCUSDT', request=request, end=2025*daily.DAY), rows)


if __name__ == '__main__':
    unittest.main()
