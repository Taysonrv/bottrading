"""Fixed, experimental Spot rules evaluated only on closed candles."""
import statistics

NAMES=('ma_cross','breakout_volume','pullback_fixed','pullback_rsi','pullback_atr','mean_reversion','vwap_filter','momentum_volume','macd_cross','ema_9_20','ema_ribbon','bollinger_squeeze','stochastic_pullback')


def ema(prices,period):
    if len(prices)<period:raise ValueError('Aquecimento insuficiente')
    value=statistics.mean(prices[:period]);a=2/(period+1)
    for p in prices[period:]:value=a*p+(1-a)*value
    return value


def rsi(prices,period=14):
    if len(prices)<=period:raise ValueError('Aquecimento insuficiente')
    changes=[b-a for a,b in zip(prices,prices[1:])]
    gain=statistics.mean(max(c,0) for c in changes[:period]);loss=statistics.mean(max(-c,0) for c in changes[:period])
    for c in changes[period:]:
        gain=(gain*(period-1)+max(c,0))/period;loss=(loss*(period-1)+max(-c,0))/period
    return 50. if gain==loss==0 else 100. if loss==0 else 100-100/(1+gain/loss)


def atr(rows,period=14):
    if len(rows)<=period:raise ValueError('Aquecimento insuficiente')
    return statistics.mean(max(b['high']-b['low'],abs(b['high']-a['close']),abs(b['low']-a['close'])) for a,b in zip(rows[-period-1:-1],rows[-period:]))


def vwap(rows):
    volume=sum(r.get('volume',0) for r in rows)
    if volume<=0:raise ValueError('Volume ausente')
    # Candle proxy, not tick/session VWAP or volume profile.
    return sum((r['high']+r['low']+r['close'])/3*r['volume'] for r in rows)/volume


def macd(prices):
    values=[ema(prices[:i],12)-ema(prices[:i],26) for i in range(26,len(prices)+1)]
    return values[-1]-ema(values,9)


def stochastic(rows,period=14):
    if len(rows)<period:raise ValueError('Aquecimento insuficiente')
    recent=rows[-period:];low=min(r['low'] for r in recent);high=max(r['high'] for r in recent)
    return 50. if high==low else 100*(recent[-1]['close']-low)/(high-low)


def bollinger(prices):
    recent=prices[-20:];mean=statistics.mean(recent);sigma=statistics.pstdev(recent)
    return mean,mean+2*sigma,4*sigma/mean


def decision(name,rows,position,fee=.001,slip=.001):
    if name not in NAMES or len(rows)<60:raise ValueError('Regra ou aquecimento inválido')
    prices=[r['close'] for r in rows];last=prices[-1]
    fast,slow=ema(prices,20),ema(prices,50)
    trend=fast>slow and last>slow
    pull=trend and last<=fast*1.005 and last/prices[-7]-1>0
    volume=rows[-1].get('volume',0);average=statistics.mean(r.get('volume',0) for r in rows[-21:-1])
    bought=position['units']>1e-12
    gain=position['units']*last*(1-slip)*(1-fee)/position['cost']-1 if bought else 0
    buy=sell=False;distance=None
    if name=='ma_cross':
        now=ema(prices,9)-ema(prices,21);before=ema(prices[:-1],9)-ema(prices[:-1],21)
        buy=before<=0<now and trend;sell=before>=0>now
    elif name=='breakout_volume':
        buy=trend and last>max(r['high'] for r in rows[-21:-1]) and average>0 and volume>=1.5*average
        sell=last<min(r['low'] for r in rows[-11:-1])
    elif name in ('pullback_fixed','pullback_rsi','pullback_atr'):
        buy=pull and (name!='pullback_rsi' or 40<=rsi(prices)<=65)
        sell=last<statistics.mean(prices[-20:])
        if name=='pullback_atr':
            distance=2*atr(rows)
            buy=buy and distance>0
            sell=sell or bought and (last<=position.get('atr_stop',0) or last>=position.get('atr_target',float('inf')))
    elif name=='mean_reversion':
        travel=sum(abs(b-a) for a,b in zip(prices[-21:-1],prices[-20:]))
        efficiency=abs(last-prices[-21])/travel if travel else 0
        mean=statistics.mean(prices[-20:]);sigma=statistics.pstdev(prices[-20:])
        buy=efficiency<.3 and sigma>0 and last<mean-2*sigma and rsi(prices)<30
        sell=last>=mean or efficiency>=.6
    elif name=='vwap_filter':
        buy=trend and last>vwap(rows[-20:]) and prices[-2]<=vwap(rows[-21:-1])
        sell=last<vwap(rows[-20:])
    elif name=='momentum_volume':
        buy=trend and last/prices[-7]-1>=.01 and average>0 and volume>=2*average
        sell=last<fast or last/prices[-4]-1<0
    elif name=='macd_cross':
        buy=macd(prices[:-1])<=0<macd(prices) and trend
        sell=macd(prices[:-1])>=0>macd(prices)
    elif name=='ema_9_20':
        now=ema(prices,9)-ema(prices,20);before=ema(prices[:-1],9)-ema(prices[:-1],20)
        buy=before<=0<now and trend and rsi(prices)>50;sell=now<0
    elif name=='ema_ribbon':
        e5,e8,e13=[ema(prices,n) for n in (5,8,13)]
        before5=ema(prices[:-1],5);before_max=max(ema(prices[:-1],8),ema(prices[:-1],13))
        buy=trend and before5<=before_max and e5>e8>e13 and last>e5
        sell=e5<e8 and e5<e13
    elif name=='bollinger_squeeze':
        mean,upper,width=bollinger(prices);_,_,previous_width=bollinger(prices[:-1])
        tight=all(bollinger(prices[:end])[2]<=.02 for end in range(len(prices)-5,len(prices)))
        buy=trend and tight and last>upper and width>previous_width*1.1 and average>0 and volume>=1.5*average
        sell=last<mean
    elif name=='stochastic_pullback':
        k=stochastic(rows);before=stochastic(rows[:-1])
        d=statistics.mean(stochastic(rows[:end]) for end in range(len(rows)-2,len(rows)+1))
        previous_d=statistics.mean(stochastic(rows[:end]) for end in range(len(rows)-3,len(rows)))
        buy=trend and before<20 and before<=previous_d and k>d
        sell=k>80 or k<d
    if bought and name!='pullback_atr':sell=sell or gain<=-.02 or gain>=.01
    return dict(buy=bool(buy and not bought),sell=bool(sell and bought),distance=distance)
