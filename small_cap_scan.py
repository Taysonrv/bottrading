"""Public-market feasibility scan for a 20-USDT paper account. No broker."""
import datetime as dt
from decimal import Decimal, ROUND_DOWN
import json
from pathlib import Path
import statistics
import time
from market_view import public_get
from local_reports import destination
import research

CAPITAL=20
FEE=Decimal('.001')
SLIPPAGE=Decimal('.001')
EXCLUDED={'USDC','FDUSD','USDP','TUSD','DAI','USDE','USD1','USDD','EUR','EURI','BRL','TRY','AEUR','PAXG','XAUT'}
CRYPTO_BASES=set('BTC ETH BNB SOL XRP DOGE ADA AVAX LINK DOT LTC BCH NEAR UNI SUI HBAR TRX ATOM AAVE ETC FIL OP ARB INJ TON ZEC WLD PEPE ENA HYPE PUMP'.split())


def universe(info,tickers):
    metadata={s['symbol']:s for s in info['symbols'] if s.get('status')=='TRADING'
              and s.get('quoteAsset')=='USDT' and s.get('isSpotTradingAllowed') is True
              and s.get('baseAsset') not in EXCLUDED
              and s.get('baseAsset') in CRYPTO_BASES
              and not s.get('baseAsset','').endswith(('UP','DOWN','BULL','BEAR'))}
    liquid=[]
    for ticker in tickers:
        symbol=ticker.get('symbol')
        if symbol not in metadata:
            continue
        volume=Decimal(ticker['quoteVolume'])
        if volume.is_finite() and volume>=Decimal('10000000'):
            liquid.append((volume,symbol))
    return [metadata[s] for _,s in sorted(liquid,key=lambda x:(-x[0],x[1]))[:20]]


def assess(meta,quote,candles,end_ms):
    bid,ask=Decimal(quote['bidPrice']),Decimal(quote['askPrice'])
    if not bid.is_finite() or not ask.is_finite() or not 0<bid<=ask:
        raise ValueError('Bid/ask inválidos')
    filters={f['filterType']:f for f in meta['filters']}
    lot=filters['LOT_SIZE']
    step=Decimal(lot['stepSize'])
    if step<=0:
        raise ValueError('Lote inválido')
    minimum=max([Decimal(f['minNotional']) for f in meta['filters']
                 if f['filterType'] in ('MIN_NOTIONAL','NOTIONAL')]+[Decimal(0)])
    budget=Decimal(CAPITAL)*Decimal('.05')
    # Conservative quote budget includes adverse fill and fee. Never round up to exchange minimum.
    price=ask*(1+SLIPPAGE)
    quantity=(budget/(price*(1+FEE))/step).to_integral_value(rounding=ROUND_DOWN)*step
    notional=quantity*ask
    spread=ask/bid-1
    reasons=[]
    if quantity<Decimal(lot['minQty']) or notional<minimum:
        reasons.append('Ordem de até 1 USDT abaixo do mínimo/lote')
    if quantity>Decimal(lot['maxQty']):
        reasons.append('Quantidade acima do máximo')
    if 'NOTIONAL' in filters and notional>Decimal(filters['NOTIONAL']['maxNotional']):
        reasons.append('Valor acima do máximo')
    if spread>Decimal('.001'):
        reasons.append('Spread acima de 0,10%')
    closed=[r for r in candles if int(r[6])<end_ms]
    rows=[dict(open_time=int(r[0]),open=float(r[1]),high=float(r[2]),low=float(r[3]),close=float(r[4])) for r in closed]
    research.check_rows(rows,60,step=3600000)
    if rows[-1]['open_time']!=end_ms-3600000:
        raise ValueError('Candles desatualizados')
    prices=[r['close'] for r in rows]
    fast,slow=statistics.mean(prices[-20:]),statistics.mean(prices[-50:])
    momentum=prices[-1]/prices[-7]-1
    signal=prices[-1]>fast>slow and momentum>0
    if not signal:
        reasons.append('Sem sinal de tendência de alta')
    return dict(symbol=meta['symbol'],minimum=float(minimum),budget=float(budget),
                quantity=float(quantity),estimated_cost=float(quantity*price*(1+FEE)),
                spread=float(spread),momentum=momentum,signal=signal,
                eligible=not reasons,reasons=reasons,score=momentum-float(spread)-.004)


def scan(get=public_get,now=None):
    now=time.time() if now is None else now
    end=int(now*1000)//3600000*3600000
    candidates=universe(get('exchangeInfo'),get('ticker/24hr'))
    quotes={q['symbol']:q for q in get('ticker/bookTicker')}
    results=[]
    for meta in candidates:
        symbol=meta['symbol']
        try:
            candles=get(f'klines?symbol={symbol}&interval=1h&limit=60&startTime={end-60*3600000}&endTime={end-1}')
            results.append(assess(meta,quotes[symbol],candles,end))
        except (KeyError,ValueError,ArithmeticError,OSError) as error:
            results.append(dict(symbol=symbol,eligible=False,reasons=['Dados indisponíveis ou inválidos'],error=type(error).__name__))
    results.sort(key=lambda r:(not r['eligible'],-r.get('score',-999),r['symbol']))
    eligible=[r for r in results if r['eligible']]
    return dict(created=dt.datetime.now(dt.timezone.utc).isoformat(),capital=CAPITAL,cash=CAPITAL,
                equity=CAPITAL,orders=[],positions={},approved=False,mode='feasibility',
                selected=eligible[0]['symbol'] if eligible else None,results=results,
                note='Observação de viabilidade; nenhum sinal validado para execução. Máximo uma posição futura. Custos são hipóteses, não taxas da conta.')


def main():
    report=scan()
    path=destination(Path(__file__).resolve().parent,'small-cap-scan.json')
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(f"Capital fictício: 20 USDT; orçamento por ordem: 1 USDT; pares avaliados: {len(report['results'])}.")
    for r in report['results']:
        print(r['symbol'], 'sinal de alta' if r.get('signal') else 'sem sinal', '; '.join(r['reasons']) or 'Candidato apenas para pesquisa')
    print('Seleção:',report['selected'] or 'Nenhuma. Saldo preservado em USDT fictícios.')


if __name__=='__main__':
    main()
