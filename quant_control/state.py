"""Compact numeric REST L1 snapshot. Missing risk fields remain null, not zero."""
import json
import math
import statistics
from spot_engine.data import milliseconds
from . import SYMBOLS


def numeric(value,low=0,high=1e15):
    if type(value) not in (float,int) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError('INVALID_NUMERIC_STATE')
    return value


def build(book,history,account,as_of_ms):
    milliseconds(as_of_ms)
    if history.symbol not in SYMBOLS or history.timeframe!='15m':raise ValueError('STATE_UNIVERSE_OR_INTERVAL')
    if book['symbol']!=history.symbol:raise ValueError('BOOK_HISTORY_MISMATCH')
    received=milliseconds(book['received_ms'])
    if not 0<=as_of_ms-received<=2000:raise ValueError('STALE_OR_FUTURE_BOOK')
    if len(history.candles)!=61:raise ValueError('REQUIRES_61_CLOSED_15M_BARS')
    bars=history.candles
    for i,c in enumerate(bars):
        if c.open_ms%900000 or c.open_ms+900000>as_of_ms:raise ValueError('FUTURE_OR_UNALIGNED_CANDLE')
        if i and c.open_ms-bars[i-1].open_ms!=900000:raise ValueError('CANDLE_GAP')
    if not 0<=as_of_ms-(bars[-1].open_ms+900000)<900000:raise ValueError('STALE_CANDLE_HISTORY')
    bid=numeric(book['bid'],1e-12);ask=numeric(book['ask'],1e-12)
    bq=numeric(book['bid_qty'],1e-12);aq=numeric(book['ask_qty'],1e-12)
    if bid>ask:raise ValueError('CROSSED_BOOK')
    mid=bid+(ask-bid)/2;scale=max(bq,aq);b,a=bq/scale,aq/scale
    returns=[math.log(y.close)-math.log(x.close) for x,y in zip(bars,bars[1:])]
    tr=[];atr=None
    for i,c in enumerate(bars):
        value=c.high-c.low if not i else max(c.high-c.low,abs(c.high-bars[i-1].close),abs(c.low-bars[i-1].close))
        if atr is None:
            tr.append(value)
            if len(tr)==14:atr=math.fsum(tr)/14
        else:atr=(atr*13+value)/14
    fields={}
    for key in ('inventory_fraction','drawdown','daily_loss'):
        value=account.get(key)
        fields[key]=None if value is None else numeric(value,0,1)
    def rounded(v):return None if v is None else float(format(v,'.9g'))
    state=dict(v=1,s=SYMBOLS.index(history.symbol),t=as_of_ms,b=bars[-1].open_ms+900000,
        mid=rounded(mid),spr=rounded((ask-bid)/mid),imb=rounded((b-a)/(b+a)),
        rv=rounded(statistics.pstdev(returns)),inv=rounded(fields['inventory_fraction']),
        dd=rounded(fields['drawdown']),dl=rounded(fields['daily_loss']),
        r1=rounded(bars[-1].close/bars[-2].close-1),
        r4=rounded(bars[-1].close/bars[-5].close-1),
        r60=rounded(bars[-1].close/bars[0].close-1),atr=rounded(atr/bars[-1].close))
    encoded=json.dumps(state,separators=(',',':'),allow_nan=False)
    if len(encoded.encode('utf-8'))>1000:raise ValueError('STATE_BYTE_BUDGET')
    return dict(numeric=state,encoded=encoded,bytes=len(encoded.encode('utf-8')),
        token_count=None,token_count_verified=False,target_tokens=400,
        source='BINANCE_PUBLIC_REST_L1',origin_timestamp_available=False,
        flow_verified=False,return_interval='15m',return_samples=60,
        received_ms=received,as_of_ms=as_of_ms,execution_authorized=False)
