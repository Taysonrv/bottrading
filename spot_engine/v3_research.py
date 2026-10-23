"""Causal v3 indicator/signal research. No execution, balances or account API.

Raw indicator readiness is not permission to trade. External event/funding/BTC
filters, risk sizing and partial exits are not implemented here. action=HOLD.
"""
from collections import deque
import math
import statistics
from .data import Candle,milliseconds

STEP=900000
SYMBOLS=('BTC/USDT','ETH/USDT','SOL/USDT','BNB/USDT','LINK/USDT','AVAX/USDT')


def ema(previous,value,n):
    return value if previous is None else previous+(value-previous)*2/(n+1)


class Wilder:
    def __init__(self,n=14):self.n=n;self.seed=[];self.value=None
    def update(self,value):
        if self.value is None:
            self.seed.append(value)
            if len(self.seed)==self.n:self.value=math.fsum(self.seed)/self.n;self.seed=[]
        else:self.value=(self.value*(self.n-1)+value)/self.n
        return self.value


class HigherClose:
    """Publish EMA only on a full UTC bucket, never a forming higher candle."""
    def __init__(self,step,period):
        self.step=step;self.period=period;self.bucket=None;self.count=0;self.first=None
        self.bars=0;self.value=None;self.close=None;self.close_ms=None
    def update(self,c):
        bucket=c.open_ms//self.step*self.step
        if bucket!=self.bucket:self.bucket=bucket;self.count=0;self.first=c.open_ms
        self.count+=1
        if c.open_ms+STEP==bucket+self.step and self.first==bucket and self.count==self.step//STEP:
            self.bars+=1;self.close=c.close;self.close_ms=c.open_ms+STEP
            self.value=ema(self.value,c.close,self.period)
    @property
    def ready(self):return self.bars>=3*self.period


def rule_decisions(f):
    """Four hypotheses share hard gates; scores never override prerequisites."""
    regime=f['regime'];context=f['context'];rsi=f['rsi']
    cross9=f['cross9'];cross_macd=f['cross_macd'];rsi35=f['rsi35']
    rules={
      'ema_ribbon':dict(regime=regime=='TREND',momentum=45<=rsi<=65 and cross_macd,
                        timing=cross9,vwap=f['close']>=f['vwap']),
      'rsi_divergence':dict(regime=regime=='RANGE',momentum=rsi35,
                        timing=f['divergence'] and f['band_recovery'],vwap=f['close']<f['vwap']),
      'breakout_volume':dict(regime=regime=='BREAKOUT',momentum=45<=rsi<=65 and f['macd']>f['macd_signal'],
                        timing=f['breakout'],vwap=f['close']>=f['vwap']),
      'vwap_reversion':dict(regime=regime=='RANGE',momentum=rsi35,
                        timing=f['band_cross'],vwap=f['close']<f['vwap'])}
    results={}
    for name,r in rules.items():
        checks=dict(trend=context and r['regime'],momentum=r['momentum'],
                    timing=r['timing'] and f['body']>=.4,
                    volatility=.005<=f['atr_fraction']<=.02,
                    volume=f['relative_volume'] is not None and f['relative_volume']>1.3 and f['obv_rising'] and r['vwap'])
        score=20*sum(checks.values())
        # All specified confirmations are hard requirements. The >=70 threshold
        # is non-binding if all five gates are mandatory, an explicit spec limit.
        eligible=f['ready'] and f['hour_allowed'] and all(checks.values()) and score>=70
        results[name]=dict(checks=checks,score_points=score,candidate=bool(eligible))
    return results


class V3Research:
    def __init__(self,symbol):
        if symbol not in SYMBOLS:raise ValueError('V3_UNIVERSE_ONLY')
        self.symbol=symbol;self.last=None;self.index=-1;self.as_of=None
        self.ema={n:None for n in (9,12,21,26,50)};self.macd_signal=None
        self.tr=Wilder();self.gain=Wilder();self.loss=Wilder()
        self.plus=Wilder();self.minus=Wilder();self.adx=Wilder()
        self.h4=HigherClose(14400000,200);self.daily=HigherClose(86400000,50)
        self.history=deque(maxlen=64);self.pivots=deque(maxlen=2);self.obv=0.
        self.day=None;self.vp=0.;self.volume=0.;self.last_rsi=None;self.last_bb=None

    def update(self,c,*,as_of_ms):
        milliseconds(as_of_ms)
        if not isinstance(c,Candle) or c.open_ms%STEP or c.open_ms+STEP>as_of_ms:
            raise ValueError('CANDLE_NOT_CLOSED_OR_ALIGNED')
        if self.last is not None and c.open_ms!=self.last.open_ms+STEP:raise ValueError('CANDLE_GAP_OR_DUPLICATE')
        if self.as_of is not None and as_of_ms<self.as_of:raise ValueError('CLOCK_REVERSED')
        if max(c.open,c.high,c.low,c.close,c.volume)>1e15 or min(c.open,c.high,c.low,c.close)<1e-12:
            raise ValueError('NUMERIC_BOUND')
        prior=self.last;previous_ema=dict(self.ema);previous_macd=None if self.ema[12] is None else self.ema[12]-self.ema[26]
        previous_macd_signal=self.macd_signal;previous_rsi=self.last_rsi;previous_bb=self.last_bb
        self.index+=1
        for n in self.ema:self.ema[n]=ema(self.ema[n],c.close,n)
        macd=self.ema[12]-self.ema[26];self.macd_signal=ema(self.macd_signal,macd,9)
        tr=c.high-c.low if prior is None else max(c.high-c.low,abs(c.high-prior.close),abs(c.low-prior.close))
        atr=self.tr.update(tr);up=c.high-prior.high if prior else 0.;down=prior.low-c.low if prior else 0.
        plus=self.plus.update(up if up>0 and up>down else 0.);minus=self.minus.update(down if down>0 and down>up else 0.)
        if atr is not None:
            pdi=100*plus/atr if atr else 0.;mdi=100*minus/atr if atr else 0.
            self.adx.update(100*abs(pdi-mdi)/(pdi+mdi) if pdi+mdi else 0.)
        rsi=None
        if prior:
            delta=c.close-prior.close;g=self.gain.update(max(0,delta));loss=self.loss.update(max(0,-delta))
            if g is not None:rsi=50. if g==loss==0 else 100. if loss==0 else 100-100/(1+g/loss)
            self.obv+=c.volume if delta>0 else -c.volume if delta<0 else 0.
        recent=list(self.history);prior20=recent[-20:]
        relative=c.volume/(sum(x['c'].volume for x in prior20)/20) if len(prior20)==20 and sum(x['c'].volume for x in prior20)>0 else None
        closes=[x['c'].close for x in recent[-19:]]+[c.close]
        mid=statistics.mean(closes) if len(closes)==20 else None
        sigma=statistics.pstdev(closes) if len(closes)==20 else None
        bb=mid-2*sigma if mid is not None else None
        upper=mid+2*sigma if mid is not None else None
        day=c.open_ms//86400000
        if day!=self.day:self.day=day;self.vp=self.volume=0.
        self.vp+=(c.high+c.low+c.close)/3*c.volume;self.volume+=c.volume
        vwap=self.vp/self.volume if self.volume else None
        self.h4.update(c);self.daily.update(c)
        row=dict(c=c,rsi=rsi,index=self.index,obv=self.obv);self.history.append(row)
        five=list(self.history)[-5:]
        if len(five)==5:
            pivot=five[2]
            if pivot['rsi'] is not None and all(pivot['c'].low<x['c'].low for i,x in enumerate(five) if i!=2):
                self.pivots.append(dict(price=pivot['c'].low,rsi=pivot['rsi'],index=pivot['index'],confirmed_ms=c.open_ms+STEP))
        divergence=False
        if len(self.pivots)==2:
            a,b=self.pivots;gap=b['index']-a['index']
            divergence=5<=gap<=32 and b['price']<a['price'] and b['rsi']>=a['rsi']+5 and self.index-b['index']<=32
        ready=self.h4.ready and self.daily.ready and rsi is not None and self.adx.value is not None and vwap is not None
        fraction=atr/c.close if atr is not None else None
        prior_high=max(x['c'].high for x in prior20) if len(prior20)==20 else None
        breakout=prior_high is not None and c.close>prior_high
        adx=self.adx.value
        regime='UNKNOWN'
        if ready:
            if fraction>.03:regime='CRISIS'
            elif adx>25 and breakout and relative is not None and relative>1.3:regime='BREAKOUT'
            elif adx>25 and self.ema[9]>self.ema[21]>self.ema[50]:regime='TREND'
            elif adx<20 and rsi<45 and c.close<vwap:regime='RANGE'
            else:regime='TRANSITION'
        f=dict(regime=regime,context=ready and self.h4.close>self.h4.value and self.daily.close>self.daily.value,
            rsi=rsi if rsi is not None else 50.,ready=ready,close=c.close,vwap=vwap if vwap is not None else c.close,
            cross9=previous_ema[9] is not None and previous_ema[9]<=previous_ema[21] and self.ema[9]>self.ema[21],
            cross_macd=previous_macd is not None and previous_macd<=previous_macd_signal and macd>self.macd_signal,
            rsi35=previous_rsi is not None and previous_rsi<=35 and rsi is not None and rsi>35,
            macd=macd,macd_signal=self.macd_signal,divergence=divergence,
            band_recovery=bb is not None and c.close>=bb,
            band_cross=prior is not None and previous_bb is not None and prior.close<previous_bb and bb is not None and c.close>=bb,
            breakout=breakout,body=abs(c.close-c.open)/(c.high-c.low) if c.high>c.low else 0.,
            atr_fraction=fraction if fraction is not None else 0.,relative_volume=relative,
            obv_rising=len(recent)>=5 and self.obv>recent[-5]['obv'],hour_allowed=not 5<=(c.open_ms+STEP)//3600000%24<9)
        rules=rule_decisions(f);candidates=sorted(n for n,r in rules.items() if r['candidate'])
        self.last=c;self.last_rsi=rsi;self.last_bb=bb;self.as_of=as_of_ms
        return dict(symbol=self.symbol,decision_ms=c.open_ms+STEP,ready=bool(ready),regime=regime,
            h4_close_ms=self.h4.close_ms,daily_close_ms=self.daily.close_ms,
            h4_bars=self.h4.bars,daily_bars=self.daily.bars,rsi14=rsi,adx14=adx,
            atr14=atr,atr_fraction=fraction,vwap=vwap,volume_relative20=relative,ema=dict(self.ema),
            macd12_26=macd,macd_signal9=self.macd_signal,obv=self.obv,
            bollinger20=dict(lower=bb,middle=mid,upper=upper),
            divergence_confirmed=bool(divergence),pivot_confirmations=list(self.pivots),rules=rules,
            research_candidate=candidates[0] if candidates else None,action='HOLD',
            execution_authorized=False,external_filters='NOT_CONNECTED',
            status='INDICATOR_RESEARCH_ONLY',note='No sizing, exits, external filters or trading approval.')


def scan(history):
    if history.timeframe!='15m':raise ValueError('V3_REQUIRES_15M')
    milliseconds(history.observed_ms)
    if not history.candles or history.candles[-1].open_ms+STEP>history.observed_ms:raise ValueError('INVALID_OBSERVATION_TIME')
    engine=V3Research(history.symbol)
    for c in history.candles:yield engine.update(c,as_of_ms=c.open_ms+STEP)


def main():
    import argparse,json
    from pathlib import Path
    from .data import load_history
    parser=argparse.ArgumentParser(description='V3 offline: quatro hipóteses, sem execução.')
    parser.add_argument('--csv',type=Path,required=True);args=parser.parse_args()
    counts={};last=None;bars=0;ready_bars=0;regimes={};failures={}
    for row in scan(load_history(args.csv)):
        last=row;bars+=1
        regimes[row['regime']]=regimes.get(row['regime'],0)+1
        if row['ready']:ready_bars+=1
        for n,r in row['rules'].items():
            counts[n]=counts.get(n,0)+int(r['candidate'])
            if row['ready']:
                target=failures.setdefault(n,{})
                for check,passed in r['checks'].items():target[check]=target.get(check,0)+int(not passed)
    print(json.dumps(dict(last=last,bars=bars,ready_bars=ready_bars,regime_counts=regimes,
                         candidate_counts=counts,failed_checks_after_warmup=failures,
                         note='Multiple checks may fail on the same bar; do not add counts. Signals are not fills.',
                         backtested=False,approved=False),allow_nan=False,indent=2))


if __name__=='__main__':main()
