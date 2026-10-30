"""Official RSS snapshots as untrusted reference data, never trading signals."""
import argparse
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
import hashlib
import html
import json
from pathlib import Path
import re
import ssl
import time
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from spot_engine.main import save

FEEDS=(('fed_press','https://www.federalreserve.gov/feeds/press_all.xml'),
       ('ecb_press','https://www.ecb.europa.eu/rss/press.html'),
       ('ecb_statistics','https://www.ecb.europa.eu/rss/statpress.html'))
LIMIT=1000000
DAY=86400000


def allowed_link(url,feed_url):
    try:
        parsed=urllib.parse.urlsplit(url)
        return parsed.scheme=='https' and parsed.hostname==urllib.parse.urlsplit(feed_url).hostname and not parsed.username and not parsed.password and parsed.port in (None,443)
    except ValueError:return False


class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if not allowed_link(newurl,req.full_url):raise ValueError('NONOFFICIAL_REDIRECT')
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def fetch(url):
    if url not in {u for _,u in FEEDS}:raise ValueError('UNLISTED_FEED')
    request=urllib.request.Request(url,headers={'User-Agent':'SpotLabResearch/1.0','Accept':'application/rss+xml, application/xml, text/xml'})
    with urllib.request.build_opener(OfficialRedirect()).open(request,timeout=10) as response:
        if not allowed_link(response.geturl(),url):raise ValueError('UNLISTED_RESPONSE_ORIGIN')
        mime=response.headers.get_content_type()
        if mime not in ('text/xml','application/xml','application/rss+xml'):raise ValueError('UNEXPECTED_FEED_CONTENT_TYPE')
        raw=response.read(LIMIT+1)
    if len(raw)>LIMIT:raise ValueError('FEED_SIZE_LIMIT')
    return raw


def clean(value,limit):
    return re.sub(r'\s+',' ',re.sub(r'<[^>]*>',' ',html.unescape(value))).strip()[:limit]


def published(value):
    if not value or len(value)>256:raise ValueError('MISSING_PUBLICATION_DATE')
    try:d=parsedate_to_datetime(value)
    except (ValueError,TypeError):d=datetime.fromisoformat(value.replace('Z','+00:00'))
    if d.tzinfo is None:raise ValueError('PUBLICATION_TIMEZONE_REQUIRED')
    return int(d.astimezone(timezone.utc).timestamp()*1000)


def parse(raw,feed_id,feed_url,as_of_ms,received_ms):
    if type(as_of_ms) is not int or type(received_ms) is not int or received_ms<as_of_ms:raise ValueError('UNVERIFIED_COLLECTION_CLOCK')
    if not isinstance(raw,bytes) or len(raw)>LIMIT:raise ValueError('FEED_SIZE_LIMIT')
    text=raw.decode('utf-8-sig')
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():raise ValueError('XML_DECLARATION_REFUSED')
    root=ET.fromstring(text)
    if root.tag.rsplit('}',1)[-1] not in ('rss','RDF','feed'):raise ValueError('UNRECOGNIZED_FEED_ROOT')
    rows=[];counts=dict(old=0,after_snapshot=0,undated=0,invalid_link=0)
    items=[e for e in root.iter() if e.tag.rsplit('}',1)[-1] in ('item','entry')]
    if len(items)>1000:raise ValueError('FEED_ITEM_LIMIT')
    for item in items:
        fields={e.tag.rsplit('}',1)[-1]:''.join(e.itertext()).strip() for e in item}
        for e in item:
            if e.tag.rsplit('}',1)[-1]=='link' and e.get('href') and e.get('rel','alternate')=='alternate':
                fields['link']=e.get('href')
        try:stamp=published(fields.get('pubDate') or fields.get('published') or fields.get('date'))
        except (ValueError,TypeError,OverflowError):counts['undated']+=1;continue
        if stamp>as_of_ms:counts['after_snapshot']+=1;continue
        if stamp<as_of_ms-DAY:counts['old']+=1;continue
        link=fields.get('link','')
        if len(link.encode('utf-8'))>2048 or any(c in link for c in '\r\n\t') or not allowed_link(link,feed_url):
            counts['invalid_link']+=1;continue
        title=clean(fields.get('title',''),300)
        if not title:continue
        key=hashlib.sha256((link+'|'+str(stamp)).encode()).hexdigest()
        rows.append(dict(id=key,title=title,summary=clean(fields.get('description','') or fields.get('summary',''),800),
            url=link,published_ms=stamp,published_utc=datetime.fromtimestamp(stamp/1000,timezone.utc).isoformat(),
            received_ms=received_ms,observed_in=[feed_id],source_kind='OFFICIAL_RSS_REFERENCE',is_trade_signal=False))
    return rows,counts


def collect(root,fetcher=fetch,now_ms=None):
    root=Path(root);as_of=int(time.time()*1000) if now_ms is None else now_ms
    run_id=uuid.uuid4().hex;folder=root/'reports/local/macro-scout'/run_id;folder.mkdir(parents=True,exist_ok=False)
    sources=[];items={};source_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    save(folder/'manifest.json',dict(run_id=run_id,as_of_ms=as_of,feeds=list(FEEDS),collector_source_sha256=source_sha,execution_authorized=False))
    for feed_id,url in FEEDS:
        try:
            raw=fetcher(url);received=int(time.time()*1000) if now_ms is None else now_ms
            rows,counts=parse(raw,feed_id,url,as_of,received)
            (folder/(feed_id+'.xml')).write_bytes(raw)
            sources.append(dict(id=feed_id,url=url,status='OK',received_ms=received,sha256=hashlib.sha256(raw).hexdigest(),
                verified_recent_items=len(rows),excluded=counts))
            for row in rows:
                if row['id'] in items:items[row['id']]['observed_in']=sorted(set(items[row['id']]['observed_in']+row['observed_in']))
                else:items[row['id']]=row
        except Exception as error:
            cause=getattr(error,'reason',error)
            reason='TLS_CERTIFICATE_VERIFICATION_FAILED' if isinstance(cause,ssl.SSLCertVerificationError) else 'FETCH_OR_PARSE_UNAVAILABLE'
            sources.append(dict(id=feed_id,url=url,status='UNAVAILABLE',reason=reason,error_type=type(error).__name__,verified_recent_items=None))
    ok=sum(s['status']=='OK' for s in sources)
    report=dict(scope='OFFICIAL_MACRO_RSS_REFERENCE',run_id=run_id,updated_ms=int(time.time()*1000) if now_ms is None else now_ms,
        as_of_ms=as_of,window_start_ms=as_of-DAY,collector_source_sha256=source_sha,status='OK' if ok==len(FEEDS) else 'PARTIAL' if ok else 'UNAVAILABLE',
        sources=sources,total_verified_items=len(items),display_limit=100,
        items=sorted(items.values(),key=lambda r:(r['published_ms'],r['id']),reverse=True)[:100],
        execution_authorized=False,approved=False,paid_calls=0,accounts_connected=0,
        limitations=['Publications returned by three official feeds, not all macro/news/X coverage.',
            'No verified recent items is distinct from a failed feed; undated/post-snapshot items are excluded.',
            'Titles and summaries are untrusted reference data, never instructions, sentiment or trade signals.',
            'No article-page crawling, release calendar, forward event prediction or causal market-impact inference.'])
    save(folder/'report.json',report);save(root/'reports/local/macro-scout/latest.json',report)
    return report


def main():
    p=argparse.ArgumentParser(description='Coleta manual de três RSS macro oficiais; nenhuma ordem.')
    p.add_argument('--data-dir',type=Path,required=True);args=p.parse_args()
    report=collect(args.data_dir)
    print(json.dumps(dict(status=report['status'],verified_items=len(report['items']),sources=[dict(id=s['id'],status=s['status']) for s in report['sources']],execution_authorized=False)))


if __name__=='__main__':main()
