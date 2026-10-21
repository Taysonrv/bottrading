"""Read-only projection of the isolated Kronos forecast, not the trading engine."""
import json
from pathlib import Path
from spot_engine.kronos_lab import summarize


def load(root):
    candidates=[Path(root).resolve()/'reports/local/kronos-lab/latest.json']
    local=Path(__file__).resolve().parent/'reports/local/kronos-lab/latest.json'
    if local not in candidates:candidates.append(local)
    for path in candidates:
        if not path.is_file():continue
        try:
            if path.stat().st_size>1_000_000:raise ValueError
            r=json.loads(path.read_text(encoding='utf-8'))
            if r.get('scope')!='KRONOS_OBSERVE_ONLY' or r.get('orders')!=0 or r.get('approved') is not False or r.get('symbol')!='BTC/USDT' or r.get('timeframe')!='1h':raise ValueError
            for key in ('cutoff_ms','issued_ms','samples','horizon'):
                if type(r[key]) is not int or r[key]<0:raise ValueError
            if r['samples']!=len(r['paths']) or not r['cutoff_ms']<=r['issued_ms']<r['cutoff_ms']+3600000:raise ValueError
            bands=summarize(r['paths'],r['horizon'])
            if bands!=r['bands']:raise ValueError
            anchor=float(r['anchor_close'])
            if not 0<anchor<1e10:raise ValueError
            return dict(available=True,issued_ms=r['issued_ms'],cutoff_ms=r['cutoff_ms'],
                        samples=r['samples'],horizon=r['horizon'],anchor_close=anchor,
                        paths=r['paths'],bands=bands,approved=False,
                        note='Amostras do modelo, não probabilidades calibradas. Nenhuma ordem, sinal de entrada ou lucro calculado.')
        except (OSError,ValueError,KeyError,TypeError):return dict(available=False,status='invalid')
    return dict(available=False,status='missing')
