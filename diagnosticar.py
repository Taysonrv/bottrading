"""Public-data diagnostics. Never imports an execution adapter or sends orders."""
import json
from pathlib import Path
import time
import urllib.error
from market_view import public_get, live_symbol
from paper_lab import save
import research

ROOT=Path(__file__).resolve().parent


def inspect(root, get=public_get, now=None):
    fixed_now=now is not None
    now=time.time() if now is None else now
    checks=[]
    def add(name,ok,detail):checks.append(dict(check=name,ok=ok,detail=detail))
    path=Path(root)/'reports/local/live-small-paper.json'
    try:
        state=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(state,dict):raise ValueError()
    except (OSError,ValueError):
        state={};add('relatorio',False,'Relatório ausente ou ilegível; não foi alterado.')
    else:
        add('relatorio',True,'Última fase: '+str(state.get('phase','indisponível'))[:30])
    add('stop',not(Path(root)/'STOP').exists(),'A trava STOP não é removida por este diagnóstico.')
    try:
        server=int(get('time')['serverTime'])/1000
        delta=abs(server-time.time()) if not fixed_now else abs(server-now)
        add('relogio',delta<=30,f'Diferença aproximada: {delta:.1f}s; inclui tempo da consulta.')
    except (OSError,ValueError,TypeError,KeyError):
        add('relogio',False,'Não foi possível consultar o horário público.')
    symbol=(state.get('position') or {}).get('symbol','BTCUSDT')
    if not live_symbol(symbol):
        add('par',False,'Par fora da lista permitida. Nenhuma consulta desse par feita.')
        return dict(created=now,symbol=None,checks=checks,trading_enabled=False)
    try:
        q=get('ticker/bookTicker?symbol='+symbol)
        import math
        bid,ask=float(q['bidPrice']),float(q['askPrice'])
        valid=all(math.isfinite(v) and v>0 for v in (bid,ask)) and ask>=bid
        add('cotacao',valid,'Bid/ask públicos válidos.' if valid else 'Bid/ask inválidos.')
    except (OSError,ValueError,TypeError,KeyError):
        add('cotacao',False,'Consulta pública de bid/ask falhou.')
    hour=int(now)//3600;end=hour*3600000
    try:
        raw=get(f'klines?symbol={symbol}&interval=1h&limit=60&startTime={end-60*3600000}&endTime={end-1}')
        rows=[dict(open_time=int(r[0]),open=float(r[1]),high=float(r[2]),low=float(r[3]),close=float(r[4])) for r in raw]
        research.check_rows(rows,60)
        if rows[-1]['open_time']!=end-3600000:raise ValueError()
        add('candles',True,'60 candles horários fechados, contínuos e recentes para o par consultado.')
    except (OSError,ValueError,TypeError,KeyError,IndexError):
        add('candles',False,'Histórico indisponível, atrasado, com lacunas ou OHLC inválido. Pode ocorrer na virada da hora; confira novamente no próximo ciclo.')
    return dict(created=now,symbol=symbol,checks=checks,trading_enabled=False,
                scope='Somente o par da posição, ou BTCUSDT sem posição. Não diagnostica todos os pares do universo nem prova a causa de erros anteriores.')


def main():
    report=inspect(ROOT)
    save(ROOT/'reports/local/connection-diagnostic.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    print('Somente consultas públicas. Nenhuma carteira, sessão ou trava alterada.')


if __name__=='__main__':main()
