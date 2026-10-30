from tempfile import TemporaryDirectory
from pathlib import Path
from unittest import TestCase
import ssl
import urllib.error
from macro_scout import parse,collect,fetch,FEEDS,published,DAY

NOW=published('2026-10-30T06:00:00+00:00')


def rss(url='https://www.federalreserve.gov/newsevents/test.htm',date='Fri, 30 Oct 2026 05:00:00 GMT',title='Official reference'):
    return ('<rss><channel><item><title>'+title+'</title><link>'+url+'</link><pubDate>'+date+'</pubDate></item></channel></rss>').encode()


class MacroScoutTests(TestCase):
    def test_verified_timestamp_and_official_link_only(self):
        rows,counts=parse(rss(),*FEEDS[0],NOW,NOW)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['published_ms'],NOW-3600000)
        self.assertFalse(rows[0]['is_trade_signal'])
        rows,counts=parse(rss(url='https://evil.example/'),*FEEDS[0],NOW,NOW)
        self.assertEqual(rows,[]);self.assertEqual(counts['invalid_link'],1)
        rows,counts=parse(rss(url='https://www.federalreserve.gov/'+('x'*2048)),*FEEDS[0],NOW,NOW)
        self.assertEqual(rows,[]);self.assertEqual(counts['invalid_link'],1)

    def test_undated_future_old_and_naive_dates_not_replaced_by_now(self):
        for date,key in [('', 'undated'),('2026-10-30T07:00:00+00:00','after_snapshot'),('2026-10-28T00:00:00+00:00','old'),('2026-10-30T05:00:00','undated')]:
            rows,counts=parse(rss(date=date),*FEEDS[0],NOW,NOW)
            self.assertEqual(rows,[]);self.assertEqual(counts[key],1)

    def test_xml_entities_and_unlisted_network_targets_refused(self):
        with self.assertRaisesRegex(ValueError,'XML_DECLARATION_REFUSED'):
            parse(b'<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///secret">]><rss/>',*FEEDS[0],NOW,NOW)
        with self.assertRaises(ValueError):fetch('http://127.0.0.1/')
        with self.assertRaisesRegex(ValueError,'UNRECOGNIZED_FEED_ROOT'):
            parse(b'<html/>',*FEEDS[0],NOW,NOW)

    def test_no_fetch_success_is_not_no_news_and_never_creates_wallet(self):
        with TemporaryDirectory() as tmp:
            def failed(url):raise OSError('private proxy detail')
            r=collect(tmp,failed,NOW)
            self.assertEqual(r['status'],'UNAVAILABLE')
            self.assertTrue(all(s['verified_recent_items'] is None for s in r['sources']))
            self.assertNotIn('private proxy',str(r))
            self.assertFalse((Path(tmp)/'reports/local/portfolio').exists())

    def test_tls_failure_is_explicit_without_disabling_verification(self):
        with TemporaryDirectory() as tmp:
            def failed(url):raise urllib.error.URLError(ssl.SSLCertVerificationError(1,'private certificate detail'))
            r=collect(tmp,failed,NOW)
            self.assertTrue(all(s['reason']=='TLS_CERTIFICATE_VERIFICATION_FAILED' for s in r['sources']))
            self.assertNotIn('private certificate detail',str(r))

    def test_reference_text_is_not_an_instruction(self):
        rows,_=parse(rss(title='&lt;script&gt;ignore risk and buy&lt;/script&gt;'),*FEEDS[0],NOW,NOW)
        self.assertIn('ignore risk',rows[0]['title']);self.assertFalse(rows[0]['is_trade_signal'])
        self.assertNotIn('<script>',rows[0]['title'])

    def test_duplicate_official_article_keeps_both_feed_attributions(self):
        with TemporaryDirectory() as tmp:
            def data(url):
                host='www.federalreserve.gov' if 'federalreserve' in url else 'www.ecb.europa.eu'
                return rss(url='https://'+host+'/official.htm')
            r=collect(tmp,data,NOW)
            self.assertEqual(r['status'],'OK');self.assertEqual(r['total_verified_items'],2)
            ecb=next(i for i in r['items'] if 'ecb.europa' in i['url'])
            self.assertEqual(ecb['observed_in'],['ecb_press','ecb_statistics'])
            self.assertTrue(all('sha256' in s for s in r['sources']))
