"""Offline candidate inspection. No execution client, account or wallet access.

Five 20-point checks are a rule count, NOT a probability or calibrated edge.
The existing EMA strategy and active portfolio are deliberately unchanged.
"""
from dataclasses import replace
from .config import load_settings
from .data import milliseconds
from .strategy import analyze


def inspect(history):
    cfg=replace(load_settings({'TRADING_TIMEFRAME':history.timeframe}),symbol=history.symbol)
    signals=analyze(history,cfg)  # validates ordering, gaps and closed-bar causality
    if not signals:raise ValueError('EMPTY_HISTORY')
    milliseconds(history.observed_ms)
    if signals[-1].decision_ms>history.observed_ms:
        raise ValueError('FUTURE_CANDLE')
    fast=slow=macd_signal=None;gain=loss=None;changes=[];previous=None
    for c in history.candles:
        fast=c.close if fast is None else fast+2/13*(c.close-fast)
        slow=c.close if slow is None else slow+2/27*(c.close-slow)
        macd=fast-slow
        macd_signal=macd if macd_signal is None else macd_signal+2/10*(macd-macd_signal)
        if previous is not None:
            delta=c.close-previous
            if gain is None:
                changes.append(delta)
                if len(changes)==14:
                    gain=sum(max(0,x) for x in changes)/14
                    loss=sum(max(0,-x) for x in changes)/14
            else:
                gain=(gain*13+max(0,delta))/14;loss=(loss*13+max(0,-delta))/14
        previous=c.close
    rsi=None if gain is None else 50. if gain==loss==0 else 100. if loss==0 else 100-100/(1+gain/loss)
    prior=history.candles[-21:-1]
    average=sum(c.volume for c in prior)/20 if len(prior)==20 else 0
    relative_volume=history.candles[-1].volume/average if average>0 else None
    last=signals[-1];close=history.candles[-1].close
    checks=dict(trend=close>last.ema_trend and last.ema_fast>last.ema_slow,
                momentum=rsi is not None and 50<=rsi<=70 and macd>macd_signal,
                timing=last.action=='ENTER_LONG',
                volatility=last.atr_fraction is not None and float(cfg.atr_min_fraction)<=last.atr_fraction<=float(cfg.atr_max_fraction),
                volume=relative_volume is not None and relative_volume>=1.2)
    score=20*sum(checks.values()) if last.ready else None
    candidate=last.ready and checks['trend'] and checks['timing'] and checks['volatility'] and score>=80
    return dict(version='layered_research_v1',symbol=history.symbol,timeframe=history.timeframe,
                decision_ms=last.decision_ms,ready=last.ready,checks=checks,score_points=score,
                rsi14=rsi,macd12_26=macd,macd_signal9=macd_signal,relative_volume20=relative_volume,
                candidate='RESEARCH_BUY' if candidate else 'HOLD',execution_authorized=False,
                calibrated_probability=None,validation='NOT_BACKTESTED',
                note='Point count only. Costs, filters and held-out validation still required; never connected to execution.')


def main():
    import argparse,json
    from pathlib import Path
    from .data import load_history
    parser=argparse.ArgumentParser(description='Inspeção offline; não executa ou valida rentabilidade.')
    parser.add_argument('--csv',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(inspect(load_history(args.csv)),ensure_ascii=True,allow_nan=False,indent=2))


if __name__=='__main__':main()
