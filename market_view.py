"""Read-only public candles for visualization; never calls the trading engine."""
import json
import math
import statistics
import time
import urllib.request


def public_get(path):
    with urllib.request.urlopen('https://data-api.binance.vision/api/v3/'+path,timeout=15) as response:
        return json.load(response)


def load(symbol, get=public_get, now=None):
    if symbol not in ('BTCUSDT','ETHUSDT'):
        raise ValueError('Ativo não permitido')
    now=time.time() if now is None else now
    candles=[]
    for row in get('klines?symbol='+symbol+'&interval=15m&limit=60'):
        item=dict(time=int(row[0])/1000,close_time=int(row[6])/1000,
                  open=float(row[1]),high=float(row[2]),low=float(row[3]),close=float(row[4]))
        if not all(math.isfinite(item[k]) and item[k]>0 for k in ('open','high','low','close')):
            raise ValueError('Preço inválido')
        if item['low']>min(item['open'],item['close']) or item['high']<max(item['open'],item['close']):
            raise ValueError('OHLC inválido')
        item['closed']=item['close_time']<now
        candles.append(item)
    if len(candles)<2 or not 0<=now-candles[-1]['time']<1800:
        raise ValueError('Candles atrasados')
    if any(b['time']-a['time']!=900 for a,b in zip(candles,candles[1:])):
        raise ValueError('Lacunas nos candles')
    daily=[r for r in get('klines?symbol='+symbol+'&interval=1d&limit=250') if int(r[6])/1000<now]
    if len(daily)<200 or not 0<=now-int(daily[-1][6])/1000<26*3600:
        raise ValueError('Histórico diário indisponível')
    daily=daily[-200:]
    if any(int(b[0])-int(a[0])!=86400000 for a,b in zip(daily,daily[1:])):
        raise ValueError('Lacuna diária')
    prices=[float(r[4]) for r in daily]
    if any(not math.isfinite(p) or p<=0 for p in prices):
        raise ValueError('Fechamento inválido')
    return dict(symbol=symbol,as_of=time.time(),candles=candles,sma200=statistics.mean(prices),
                last_daily_close=prices[-1],next_close_reference=statistics.mean(prices[-199:]),
                next_daily_close=(int(now)//86400+1)*86400)
