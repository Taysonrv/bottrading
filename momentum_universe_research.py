"""Test SOL/RENDER/PEPE selection with one fictitious position, never copy-trades."""
import datetime as dt
import json
from pathlib import Path
import time
from market_view import public_get
from local_reports import destination
from small_cap_research import simulate
import research

SYMBOLS=('SOLUSDT','RENDERUSDT','PEPEUSDT')


def windows(histories):
    if not histories or any(len(rows)!=780 for rows in histories.values()):
        raise ValueError('Janela fixa exige 780 barras')
    return [{s:rows[offset:offset+300] for s,rows in histories.items()} for offset in (0,240,480)]


def main():
    end=int(time.time()*1000)//3600000*3600000
    metadata={s['symbol']:s for s in public_get('exchangeInfo')['symbols']
              if s['symbol'] in SYMBOLS and s['status']=='TRADING' and s.get('isSpotTradingAllowed') is True}
    if len(metadata)!=3:raise SystemExit('Um dos pares fixos está indisponível; estudo bloqueado.')
    histories={}
    for s in SYMBOLS:
        raw=public_get(f'klines?symbol={s}&interval=1h&limit=1000&startTime={end-780*3600000}&endTime={end-1}')
        rows=[dict(open_time=int(r[0]),open=float(r[1]),high=float(r[2]),low=float(r[3]),close=float(r[4])) for r in raw]
        research.check_rows(rows,780)
        if rows[0]['open_time']!=end-780*3600000 or rows[-1]['open_time']!=end-3600000:
            raise ValueError('Dados fora do período')
        histories[s]=rows
    comparisons=[]
    for label,h in [('contínuo',histories)]+[(f'janela {i+1}',h) for i,h in enumerate(windows(histories))]:
        for stress in (1,2):
            result=simulate(h,metadata,.25,stress)
            comparisons.append(dict(window=label,**result))
    report=dict(created=dt.datetime.now(dt.timezone.utc).isoformat(),capital=20,symbols=SYMBOLS,
                start=end-720*3600000,end=end,approved=False,comparisons=comparisons,
                scope='Mesmo motor de pullback/momentum anterior; apenas o universo mudou. Não copia proporções 45/30/25.')
    destination(Path(__file__).resolve().parent,'momentum-universe.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    for r in comparisons:
        print(r['window'],r['stress'],'x',round(r['pnl'],6),'USDT',r['buys'],'compras',r['sells'],'vendas',r['blocked'],'bloqueios')
    print('Uma posição por vez; até 5 USDT por compra com custos. Sem adoção ou aprovação.')


if __name__=='__main__':main()
