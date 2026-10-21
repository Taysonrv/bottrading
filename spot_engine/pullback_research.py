"""Frozen 4h trend/1h pullback research, separate from the active paper session."""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import statistics
import uuid
from .data import Candle,PublicBinance,load_history,retry
from .minute_research import Intent,simulate
from .main import normalized_rules,save
from .scanner import SYMBOLS

H=3600000
WARMUP=2400  # 600 completed4h bars, 3*EMA200; no evaluation before this.


def hourly(history):
    """Aggregate validated15m bars into complete, UTC-aligned1h bars only."""
    if history.timeframe!='15m':raise ValueError('Expected15m source')
    result=[];group=[]
    for c in history.candles:
        if c.open_ms%H==0:group=[]
        group.append(c)
        if (c.open_ms+900000)%H==0 and len(group)==4:
            if any(b.open_ms!=group[0].open_ms+i*900000 for i,b in enumerate(group)):raise ValueError('Gap')
            result.append(Candle(group[0].open_ms,group[0].open,max(b.high for b in group),
                                 min(b.low for b in group),group[-1].close,sum(b.volume for b in group)))
            group=[]
    return tuple(result)


class Pullback:
    def __init__(self):
        self.previous=None;self.ema20=None;self.previous_touch=False
        self.ema200=None;self.four=[];self.count4=0;self.atr=None;self.seed=[]

    def update(self,c):
        if c.open_ms%H or (self.previous and c.open_ms!=self.previous.open_ms+H):raise ValueError('Hour gap')
        prev=self.previous
        tr=c.high-c.low if prev is None else max(c.high-c.low,abs(c.high-prev.close),abs(c.low-prev.close))
        if self.atr is None:
            self.seed.append(tr)
            if len(self.seed)==14:self.atr=statistics.mean(self.seed)
        else:self.atr=(13*self.atr+tr)/14
        self.ema20=c.close if self.ema20 is None else self.ema20+2/21*(c.close-self.ema20)
        if c.open_ms%(4*H)==0:self.four=[]
        self.four.append(c)
        if (c.open_ms+H)%(4*H)==0 and len(self.four)==4:
            self.ema200=c.close if self.ema200 is None else self.ema200+2/201*(c.close-self.ema200)
            self.count4+=1;self.four=[]
        result=Intent(False,'WARMUP')
        if self.count4>=600 and self.atr is not None:
            stop=max(.003,1.5*self.atr/c.close)
            if c.close<=self.ema200:result=Intent(False,'TREND_4H_FILTER')
            elif not self.previous_touch:result=Intent(False,'NO_PREVIOUS_PULLBACK')
            elif c.close<=prev.high:result=Intent(False,'NO_CONFIRMATION')
            elif stop>.03:result=Intent(False,'STOP_TOO_WIDE')
            else:result=Intent(True,'PULLBACK_CONFIRMED',stop)
        self.previous_touch=c.low<=self.ema20<=c.high
        self.previous=c
        return result


def evaluate(bars,rules):
    if len(bars)<WARMUP+4*600:raise ValueError('Short source')
    strategy=Pullback();intents=tuple(strategy.update(c) for c in bars)
    remaining=len(bars)-WARMUP
    scenarios=[]
    for label,mult in [('base',1),('double_costs',2)]:
        rows=[simulate(bars,intents,WARMUP+remaining*j//4,WARMUP+remaining*(j+1)//4,
                       rules,fee=.001*mult,slip=.001*mult,step_ms=H) for j in range(4)]
        scenarios.append(dict(name=label,windows=rows))
    return scenarios


def main():
    parser=argparse.ArgumentParser(description='Pesquisa offline de recuos1h/tendência4h. Sem ordens.')
    parser.add_argument('--data-dir',type=Path,required=True)
    args=parser.parse_args()
    # Resolve the entire fixed universe before any evaluation; no winner selection.
    paths={}
    for symbol in SYMBOLS:
        found=list(args.data_dir.glob(symbol.replace('/','-')+'-15m-*.csv'))
        if len(found)!=1:raise SystemExit('Exige exatamente um CSV15m por par, com manifesto.')
        paths[symbol]=found[0]
    histories={symbol:load_history(path) for symbol,path in paths.items()}
    if len({(h.start_ms,h.end_ms) for h in histories.values()})!=1:raise SystemExit('Janelas dos pares diferem.')
    folder=Path(__file__).resolve().parent.parent/'reports/local/spot-pullback'/uuid.uuid4().hex
    folder.mkdir(parents=True)
    index=dict(scope='PULLBACK_4H_1H_EXPLORATORY',approved=False,rows=[])
    save(folder/'index.json',index)
    client=PublicBinance()
    for symbol in SYMBOLS:
        print('Testando '+symbol,flush=True)
        try:
            bars=hourly(histories[symbol])
            rules=normalized_rules(retry(lambda:client.fetch_symbol_info(symbol)),symbol,int(retry(client.fetch_time)))
            scenarios=evaluate(bars,rules)
            report=dict(scope='CHRONOLOGICAL_EXPLORATORY_AUDIT',approved=False,
                        symbol=symbol,timeframe='1h',strategy='PULLBACK_EMA20_1H_TREND_EMA200_4H',
                        scenarios=scenarios,csv_sha256=hashlib.sha256(paths[symbol].read_bytes()).hexdigest(),
                        source_hashes={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
                                       for n in ('pullback_research.py','minute_research.py')},
                        rules={k:str(v) for k,v in vars(rules).items()},
                        caveats=['Previously examined market history; no fresh independent holdout.',
                                 'Four independent20USDT windows, no shared multi-pair equity curve.',
                                 'Current lot/notional constraints, not historical. No tick rounding, queue, spread, partial fills or measured latency.',
                                 'Synthetic stops can gap; open/close risk sampling is not continuous protection.',
                                 'Six pairs, two cost cases; no automatic approval or best-parameter selection.'])
            (folder/'reports').mkdir(exist_ok=True)
            save(folder/'reports'/(symbol.replace('/','-')+'.json'),report)
            row=dict(symbol=symbol,status='COMPLETE',base_returns=[r['net_return'] for r in scenarios[0]['windows']],
                     stress_returns=[r['net_return'] for r in scenarios[1]['windows']])
        except Exception:row=dict(symbol=symbol,status='ERROR',reason='SOURCE_OR_EXPERIMENT_FAILED')
        index['rows'].append(row);save(folder/'index.json',index)
        print(json.dumps(row),flush=True)
    print('Relatórios: '+str(folder),flush=True)


if __name__=='__main__':main()
