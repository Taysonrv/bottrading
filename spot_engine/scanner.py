"""Public multi-pair observation only; cannot submit orders or allocate capital."""
from dataclasses import replace
import argparse
import json
from pathlib import Path
import time
from .config import load_settings
from .data import PublicBinance, download, retry, STEPS
from .strategy import analyze
from .main import single_runner, save, normalized_rules, parse_book
from .selection import preview, choose

SYMBOLS = ('BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'DOGE/USDT')


def scan(client, now_ms, timeframe='15m'):
    cfg = load_settings({'TRADING_TIMEFRAME': timeframe})
    step = STEPS[cfg.timeframe]
    cutoff = now_ms // step * step
    rows = []
    for symbol in SYMBOLS:
        try:
            settings = replace(cfg, symbol=symbol)
            history = download(client, symbol, cfg.timeframe, cutoff-620*step, cutoff)
            signal = analyze(history, settings)[-1]
            # Added diagnostics only. A short history cannot warm up V3 HTFs;
            # do not let this UNKNOWN annotation change the original EMA signal.
            from v3_engine.scanner import quick_regime
            diagnostic = quick_regime(history)
            rows.append(dict(symbol=symbol, status='OK', action=signal.action,
                             reason=signal.reason, candle_close_ms=cutoff,
                             close=history.candles[-1].close,
                             ema_fast=signal.ema_fast, ema_slow=signal.ema_slow,
                             ema_trend=signal.ema_trend, atr_fraction=signal.atr_fraction,
                             regime_v3=diagnostic))
        except Exception:
            # Never retain previous success for a failed pair or echo provider URLs.
            rows.append(dict(symbol=symbol, status='ERROR', action=None, reason='PUBLIC_DATA_UNAVAILABLE',
                             regime_v3=dict(detected='UNKNOWN',reason='DATA_UNAVAILABLE',execution_authorized=False)))
    previews=[]
    for row in rows:
        if row.get('action')!='ENTER_LONG':
            previews.append(dict(symbol=row['symbol'],eligible=False,reason='NO_ENTRY_SIGNAL',execution_authorized=False))
            continue
        try:
            symbol=row['symbol']
            rules=normalized_rules(retry(lambda:client.fetch_symbol_info(symbol)),symbol,now_ms)
            before=time.monotonic()
            bid,ask,_,_=parse_book(retry(lambda:client.fetch_book(symbol)),symbol)
            actual_ms=int(retry(client.fetch_time))
            if time.monotonic()-before>3: raise ValueError('Slow quote')
            previews.append(preview(row,rules,bid,ask,now_ms=actual_ms,quote_ms=actual_ms))
        except Exception:
            previews.append(dict(symbol=row['symbol'],eligible=False,reason='MARKET_FILTERS_UNAVAILABLE',execution_authorized=False))
    return dict(mode='OBSERVE_ONLY', updated_ms=now_ms, timeframe=cfg.timeframe,
                selection=dict(candidate=choose(previews),previews=previews,
                               hypothetical_cash='20',budget='6',execution_authorized=False,
                               note='Prévia com caixa hipotético livre. Não lê nem altera a carteira; limites diários/DD precisam ser reavaliados na execução.'),
                real_orders=0, simulated_orders=0, approved=False, pairs=rows,
                note='Sinais do último candle fechado; não são entradas acionáveis nem validação de rentabilidade.')


def main():
    parser = argparse.ArgumentParser(description='Observador de seis pares Spot; nenhuma ordem.')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeframe', choices=('15m', '1h', '4h'), default='15m')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with single_runner(args.output.with_suffix('.lock')):
        client = PublicBinance()
        deadline = time.monotonic()+24*3600
        while time.monotonic() < deadline:
            # Output lives at ROOT/reports/local; respect the dashboard global STOP.
            if (args.output.parent/'STOP').exists() or (args.output.parent.parent.parent/'STOP').exists(): break
            try:
                report = scan(client, int(retry(client.fetch_time)), args.timeframe)
            except Exception:
                report = dict(mode='OBSERVE_ONLY', updated_ms=int(time.time()*1000),
                              pairs=[], status='ERROR', real_orders=0, simulated_orders=0, approved=False)
            save(args.output, report)
            diagnostic_folder=args.output.parent/'scanner-v3'
            diagnostic_folder.mkdir(parents=True,exist_ok=True)
            summary={}
            for row in report.get('pairs',[]):
                regime=row.get('regime_v3',{}).get('detected','UNKNOWN')
                summary[regime]=summary.get(regime,0)+1
            save(diagnostic_folder/'latest.json',dict(updated_ms=report['updated_ms'],
                pairs_scanned=report.get('pairs',[]),regime_summary=summary,top_candidate=None,
                execution_authorized=False,approved=False,
                note='Quick diagnostics only; no full higher-timeframe warmup or invented score.'))
            if args.once: break
            time.sleep(60)


if __name__ == '__main__':
    main()
