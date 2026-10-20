"""Freeze a future-only comparison; each run collects closed public candles, never trades."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import time
from market_view import public_get
from small_cap_scan import universe
from small_cap_research import simulate
from local_reports import destination
import research

ROOT=Path(__file__).resolve().parent
HOUR=3600000


def identity():
    return hashlib.sha256(b''.join((ROOT/name).read_bytes() for name in
        ('prospective_research.py','small_cap_research.py','research.py'))).hexdigest()


def create_plan(metadata,now,code):
    return dict(created=dt.datetime.now(dt.timezone.utc).isoformat(),cutoff=(int(now*1000)//HOUR+1)*HOUR,
                capital=20,fraction=.25,entry_intervals=[1,24],stress=[1,2],minimum_future_hours=48,
                maximum_future_hours=168,metadata=metadata,identity=code,approved=False)


def main():
    path=destination(ROOT,'prospective-plan.json')
    if not path.exists():
        metadata={m['symbol']:m for m in universe(public_get('exchangeInfo'),public_get('ticker/24hr'))}
        plan=create_plan(metadata,time.time(),identity())
        path.write_text(json.dumps(plan,indent=2),encoding='utf-8')
    else:
        plan=json.loads(path.read_text(encoding='utf-8'))
    if plan['identity']!=identity():
        raise SystemExit('Código mudou; preserve esta pesquisa e registre outra antes de comparar.')
    end=min(int(time.time()*1000)//HOUR*HOUR,plan['cutoff']+168*HOUR)
    hours=max(0,(end-plan['cutoff'])//HOUR)
    summary=dict(created=dt.datetime.now(dt.timezone.utc).isoformat(),cutoff=plan['cutoff'],
                 future_hours=hours,minimum_future_hours=48,capital=20,approved=False,comparisons=[],
                 phase='aguardando dados futuros',excluded=[])
    if hours>=48:
        histories={};start=plan['cutoff']-60*HOUR
        for s in plan['metadata']:
            raw=public_get(f'klines?symbol={s}&interval=1h&limit=1000&startTime={start}&endTime={end-1}')
            rows=[dict(open_time=int(r[0]),open=float(r[1]),high=float(r[2]),low=float(r[3]),close=float(r[4])) for r in raw]
            try:
                research.check_rows(rows,int(60+hours))
                if rows[0]['open_time']!=start or rows[-1]['open_time']!=end-HOUR:
                    raise ValueError('Período incorreto')
            except ValueError:
                summary['excluded'].append(s);continue
            histories[s]=rows
        if not histories:
            raise SystemExit('Sem dados completos; resultado não publicado.')
        destination(ROOT,'prospective-input.json').write_text(json.dumps(histories),encoding='utf-8')
        summary['phase']='comparação parcial; sem aprovação'
        summary['comparisons']=[dict(entry_interval=interval,**simulate(histories,plan['metadata'],.25,stress,entry_interval=interval))
                                for interval in (1,24) for stress in (1,2)]
    destination(ROOT,'prospective-results.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='comparisons'},ensure_ascii=False))
    print('Capital fictício. Consultas manuais; nenhuma ordem enviada. Repita o comando após novas horas fechadas.')


if __name__=='__main__':
    main()
