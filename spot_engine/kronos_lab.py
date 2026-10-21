"""CPU-only Kronos observation experiment. No broker, keys, orders or trade signal.

Each path uses sample_count=1; upstream sample_count>1 averages paths away.
Heavy ML dependencies are lazy-loaded from a dedicated environment only.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import time
import uuid
from .data import PublicBinance,download,retry,STEPS
from .main import save

ROOT=Path(__file__).resolve().parent.parent
UPSTREAM_COMMIT='67b630e67f6a18c9e9be918d9b4337c960db1e9a'


def quantile(values,q):
    ordered=sorted(values)
    if not ordered or not 0<=q<=1 or any(not math.isfinite(v) or v<=0 for v in ordered):raise ValueError('Invalid samples')
    p=(len(ordered)-1)*q;i=int(p);j=min(i+1,len(ordered)-1)
    return ordered[i]+(ordered[j]-ordered[i])*(p-i)


def summarize(paths,horizon):
    if type(horizon) is not int or not 1<=horizon<=24 or not 1<=len(paths)<=100:raise ValueError('Invalid forecast size')
    if any(len(p)!=horizon for p in paths):raise ValueError('Path length mismatch')
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for p in paths for v in p):raise ValueError('Invalid forecast prices')
    return [dict(step=i+1,p10=quantile([p[i] for p in paths],.1),
                 p50=quantile([p[i] for p in paths],.5),p90=quantile([p[i] for p in paths],.9)) for i in range(horizon)]


def score(report,actual_closes,observed_ms):
    """Score only fully closed future hours, never the still-forming candle."""
    if report.get('scope')!='KRONOS_OBSERVE_ONLY' or report.get('orders')!=0:raise ValueError('Invalid report')
    cutoff=report['cutoff_ms'];step=STEPS['1h']
    if type(observed_ms) is not int or observed_ms<report['issued_ms']:raise ValueError('Invalid evaluation time')
    count=min(len(actual_closes),len(report['bands']),(observed_ms-cutoff)//step)
    if count<=0:return dict(status='PENDING',evaluated_steps=0,approved=False)
    actual=actual_closes[:count]
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in actual):raise ValueError('Invalid actual prices')
    errors=[abs(report['bands'][i]['p50']-v) for i,v in enumerate(actual)]
    flat=[abs(report['anchor_close']-v) for v in actual]
    coverage=sum(report['bands'][i]['p10']<=v<=report['bands'][i]['p90'] for i,v in enumerate(actual))/count
    return dict(status='COMPLETE' if count==len(report['bands']) else 'PARTIAL',evaluated_steps=count,
                median_mae=sum(errors)/count,flat_price_mae=sum(flat)/count,
                model_band_coverage=coverage,approved=False,
                note='Single forecast; overlapping horizons and small sample do not establish calibration or profit.')


def forecast(source,samples=4,horizon=24):
    if type(samples) is not int or not 1<=samples<=100 or type(horizon) is not int or not 1<=horizon<=24:raise ValueError('Invalid limits')
    commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    if commit!=UPSTREAM_COMMIT:raise ValueError('Upstream version differs from reviewed commit')
    # Refuse altered reviewed source, including staged changes.
    dirty=subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip()
    if dirty:raise ValueError('Upstream source modified')
    import numpy as np
    import pandas as pd
    import torch
    from huggingface_hub import HfApi,snapshot_download
    sys.path.insert(0,str(source.resolve()))
    from model import Kronos,KronosTokenizer,KronosPredictor
    torch.set_num_threads(4)
    versions={};locations={}
    for name in ('Kronos-small','Kronos-Tokenizer-base'):
        repo='NeoQuasar/'+name
        revision=HfApi().model_info(repo,token=False).sha
        versions[repo]=revision
        locations[name]=snapshot_download(repo,revision=revision,token=False,
                           cache_dir=str(ROOT/'reports/local/kronos-runtime/hf'),
                           allow_patterns=['config.json','model.safetensors'])
    tokenizer=KronosTokenizer.from_pretrained(locations['Kronos-Tokenizer-base'],local_files_only=True)
    model=Kronos.from_pretrained(locations['Kronos-small'],local_files_only=True)
    model.eval();tokenizer.eval()
    predictor=KronosPredictor(model,tokenizer,device='cpu',max_context=512)
    client=PublicBinance();step=STEPS['1h'];now=int(retry(client.fetch_time));cutoff=now//step*step
    history=download(client,'BTC/USDT','1h',cutoff-512*step,cutoff)
    frame=pd.DataFrame([dict(open=c.open,high=c.high,low=c.low,close=c.close,volume=c.volume) for c in history.candles])
    # Timestamps are known UTC calendar features, never future observed prices.
    x=pd.Series(pd.to_datetime([c.open_ms for c in history.candles],unit='ms',utc=True).tz_localize(None))
    y=pd.Series(pd.to_datetime([cutoff+i*step for i in range(horizon)],unit='ms',utc=True).tz_localize(None))
    paths=[];seconds=[];began=time.time()
    for i in range(samples):
        random.seed(7300+i);np.random.seed(7300+i);torch.manual_seed(7300+i)
        start=time.monotonic()
        with torch.inference_mode():
            result=predictor.predict(frame,x,y,pred_len=horizon,T=1.,top_p=.9,sample_count=1,verbose=False)
        paths.append([float(v) for v in result['close']]);seconds.append(time.monotonic()-start)
        print(f'Trajetória {i+1}/{samples}: {seconds[-1]:.2f}s',flush=True)
    bands=summarize(paths,horizon)
    issued=int(time.time()*1000)
    if issued>=cutoff+step:raise ValueError('Forecast too slow; first forecast candle already closed')
    inputs=[[c.open_ms,c.open,c.high,c.low,c.close,c.volume] for c in history.candles]
    report=dict(scope='KRONOS_OBSERVE_ONLY',symbol='BTC/USDT',timeframe='1h',orders=0,approved=False,
                cutoff_ms=cutoff,issued_ms=issued,began_ms=int(began*1000),input_candles=512,
                anchor_close=history.candles[-1].close,horizon=horizon,samples=samples,
                paths=paths,bands=bands,path_seconds=seconds,device='cpu',upstream_commit=commit,
                model_revisions=versions,seeds=[7300+i for i in range(samples)],temperature=1.,top_p=.9,
                input_sha256=hashlib.sha256(json.dumps(inputs,separators=(',',':')).encode()).hexdigest(),
                input_rows=inputs,
                adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                note='Model-generated close paths, not market probabilities or trading advice. P10/P90 is not calibrated coverage. Small CPU pilot; no PnL.')
    folder=ROOT/'reports/local/kronos-lab';folder.mkdir(parents=True,exist_ok=True)
    path=folder/(uuid.uuid4().hex+'.json')
    with path.open('x',encoding='utf-8') as output:json.dump(report,output,indent=2,allow_nan=False)
    save(folder/'latest.json',report)
    print('Previsão registrada: '+str(path),flush=True)
    return report


def main():
    parser=argparse.ArgumentParser(description='Kronos local: observação sem ordens ou serviços pagos.')
    parser.add_argument('--source',type=Path,default=ROOT/'reports/local/kronos-runtime/source')
    parser.add_argument('--samples',type=int,default=4)
    parser.add_argument('--horizon',type=int,default=24)
    parser.add_argument('--evaluate',type=Path)
    args=parser.parse_args()
    if args.evaluate:
        report=json.loads(args.evaluate.read_text(encoding='utf-8'))
        client=PublicBinance();now=int(retry(client.fetch_time));cutoff=report['cutoff_ms']
        end=min(now//STEPS['1h']*STEPS['1h'],cutoff+report['horizon']*STEPS['1h'])
        actual=[]
        if end>cutoff:actual=[c.close for c in download(client,'BTC/USDT','1h',cutoff,end).candles]
        assessment=score(report,actual,now)
        save(args.evaluate.with_name(args.evaluate.stem+'-evaluation.json'),assessment)
        print(json.dumps(assessment,indent=2))
    else:forecast(args.source,args.samples,args.horizon)


if __name__=='__main__':main()
