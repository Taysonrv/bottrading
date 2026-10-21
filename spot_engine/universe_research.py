"""Bounded public-data research batch; no broker, API key or execution approval."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import uuid
from .config import load_settings
from .data import PublicBinance, download, retry, save_history, STEPS
from .scanner import SYMBOLS
from .temporal_validation import evaluate


def research_one(client, symbol, start, end, folder):
    cfg=replace(load_settings({}),mode='backtest',symbol=symbol,timeframe='15m',
                max_order_notional=Decimal('6'))
    history=download(client,symbol,cfg.timeframe,start,end)
    csv=save_history(history,folder/'data')
    report=evaluate(history,cfg,4)
    report.update(settings={k:str(v) for k,v in asdict(cfg).items()},
                  csv_sha256=hashlib.sha256(csv.read_bytes()).hexdigest(),
                  source_hashes={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                 for name in ('config.py','strategy.py','backtest.py','temporal_validation.py','universe_research.py')})
    report['caveats'].append('Pair selected before this batch. Six pairs and two cost scenarios tested; multiple comparisons matter.')
    path=folder/'reports'/(symbol.replace('/','-')+'.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as output:
        json.dump(report,output,ensure_ascii=False,indent=2,allow_nan=False)
    return dict(symbol=symbol,status='COMPLETE',candles=len(history.candles),report=path.name,
                scenarios=[dict(name=s['name'],returns=[w['net_return'] for w in s['windows']],
                                positive_windows=s['positive_windows'],beat_buy_hold_windows=s['beat_buy_hold_windows'])
                           for s in report['scenarios']])


def main():
    root=Path(__file__).resolve().parent.parent
    folder=root/'reports/local/spot-universe'/uuid.uuid4().hex
    folder.mkdir(parents=True,exist_ok=False)
    client=PublicBinance()
    end=int(retry(client.fetch_time))//STEPS['15m']*STEPS['15m']
    end_date=datetime.fromtimestamp(end/1000,timezone.utc)
    try: start_date=end_date.replace(year=end_date.year-2)
    except ValueError: start_date=end_date.replace(year=end_date.year-2,day=28)
    start=int(start_date.timestamp()*1000)
    plan=dict(scope='SIX_PAIR_15M_EXPLORATORY',approved=False,start_ms=start,end_ms=end,
              symbols=list(SYMBOLS),timeframe='15m',capital_per_independent_trial='20',
              variants_per_pair=2,rows=[])
    from .main import save
    save(folder/'index.json',plan)
    print('Pesquisa iniciada: '+str(folder),flush=True)
    for symbol in SYMBOLS:
        print('Coletando '+symbol+'...',flush=True)
        try:
            row=research_one(client,symbol,start,end,folder)
        except Exception:
            row=dict(symbol=symbol,status='ERROR',reason='DATA_OR_RESEARCH_FAILED')
        plan['rows'].append(row)
        save(folder/'index.json',plan)
        print(json.dumps(row,ensure_ascii=False,allow_nan=False),flush=True)
    plan['complete']=all(r['status']=='COMPLETE' for r in plan['rows'])
    save(folder/'index.json',plan)
    print('Encerrado; sem aprovação e sem ordens.',flush=True)


if __name__=='__main__':
    main()
