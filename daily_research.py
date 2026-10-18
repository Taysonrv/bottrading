"""Standalone daily hypotheses. Never writes validation or trading state."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import statistics
import time
import urllib.parse
import urllib.request
import research

DAY = 86_400_000
RULES = ('sma200', 'momentum90', 'breakout55_20')


def download(symbol, days=2025, request=None, end=None):
    end = int(time.time() * 1000) // DAY * DAY if end is None else end
    if type(end) is not int or end % DAY or days < 201:
        raise ValueError('Período diário inválido')
    if request is None:
        def request(url):
            with urllib.request.urlopen(url, timeout=30) as response:
                return json.load(response)
    cursor, rows = end - days * DAY, []
    while cursor < end:
        query = urllib.parse.urlencode(dict(symbol=symbol, interval='1d', limit=1000,
                                           startTime=cursor, endTime=end - 1))
        page = request('https://data-api.binance.vision/api/v3/klines?' + query)
        if not isinstance(page, list) or not page:
            raise ValueError('Histórico diário vazio')
        batch = [dict(open_time=int(r[0]), time=int(r[6]), open=float(r[1]),
                      high=float(r[2]), low=float(r[3]), close=float(r[4])) for r in page]
        if batch[0]['open_time'] != cursor or batch[-1]['open_time'] >= end:
            raise ValueError('Histórico diário fora do período')
        rows.extend(batch)
        cursor = batch[-1]['open_time'] + DAY
    research.check_rows(rows, days, step=DAY)
    return rows


def targets(rows, rule, scaled):
    """Target at index i uses only completed bars before i; breakout is stateful."""
    if rule not in RULES:
        raise ValueError('Hipótese desconhecida')
    result, holding = [], False
    for i in range(len(rows)):
        if i < 200:
            result.append(0.)
            continue
        history = rows[:i]
        close = history[-1]['close']
        if rule == 'sma200':
            holding = close > statistics.mean(r['close'] for r in history[-200:])
        elif rule == 'momentum90':
            holding = close > history[-91]['close']
        else:
            if holding and close < min(r['low'] for r in history[-21:-1]):
                holding = False
            elif not holding and close > max(r['high'] for r in history[-56:-1]):
                holding = True
        multiplier = 1.
        if scaled:
            returns = [history[j]['close'] / history[j-1]['close'] - 1
                       for j in range(len(history)-30, len(history))]
            volatility = statistics.stdev(returns) * 365 ** .5
            multiplier = min(1., .20 / volatility) if volatility else 1.
        result.append(float(holding) * multiplier)
    return result


def evaluate(histories, config):
    timestamps = [r['open_time'] for r in next(iter(histories.values()))]
    if len(timestamps) < 2025:
        raise ValueError('Exige cinco anos de avaliação e 200 dias de aquecimento')
    for rows in histories.values():
        research.check_rows(rows, step=DAY)
        if [r['open_time'] for r in rows] != timestamps:
            raise ValueError('Ativos desalinhados')
    count = len(timestamps)
    a, b = 200 + (count-200)*60//100, 200 + (count-200)*80//100
    windows = {'development': (200, a), 'evaluation_1': (a, (a+b)//2),
               'evaluation_2': ((a+b)//2, b), 'final_reused': (b, count),
               'continuous': (200, count)}
    comparisons = {}
    for rule in RULES:
        for scaled in (False, True):
            schedule = {s: targets(rows, rule, scaled) for s, rows in histories.items()}
            callback = lambda symbol, i: schedule[symbol][i]
            def run(start, end, **options):
                return research.backtest(histories, start, end, config, rule, None,
                                         target_at=callback, **options)
            results = {name: run(*window) for name, window in windows.items()}
            results['stress'] = run(b, count, stress=2)
            results['existing'] = run(b, count, initial_exposure=.8)
            results['qualified_historical'] = all(r['passed'] for r in results.values())
            comparisons[rule + ('_vol' if scaled else '_fixed')] = results
    return comparisons


def main():
    root = Path(__file__).resolve().parent
    config = json.loads((root / 'config.json').read_text(encoding='utf-8'))
    cutoff = int(time.time() * 1000) // DAY * DAY
    histories = {s: download(s, end=cutoff) for s in ('BTCUSDT', 'ETHUSDT')}
    comparisons = evaluate(histories, config)
    report = dict(created=dt.datetime.now(dt.timezone.utc).isoformat(),
                  adopted=False, independent_out_of_sample=False,
                  note='O último ano já foi consultado. Confirmação exige dados futuros.',
                  data_hash=hashlib.sha256(json.dumps(histories, sort_keys=True).encode()).hexdigest(),
                  code_hash=hashlib.sha256(b''.join((root / name).read_bytes() for name in
                                          ('daily_research.py', 'research.py', 'execution.py'))).hexdigest(),
                  config=config, comparisons=comparisons)
    output = root / 'reports' / '2026-10-18-daily-results.json'
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    lines = ['# Hipóteses diárias — resultado histórico', '', report['note'], '',
             'Nenhuma adoção ou liberação para trading. Seis tentativas, sem otimização.', '',
             '| Hipótese | Retorno contínuo | Benchmark 50/50 | Drawdown contínuo | Retorno final | Qualificada historicamente |',
             '|---|---:|---:|---:|---:|---|']
    for name, result in comparisons.items():
        r, f = result['continuous'], result['final_reused']
        lines.append(f"| {name} | {r['return']:.2%} | {r['benchmark']:.2%} | {r['drawdown']:.2%} | {f['return']:.2%} | {'Sim' if result['qualified_historical'] else 'Não'} |")
    lines += ['', '2025 candles diários fechados: 200 de aquecimento e 1825 de avaliação.',
              'Sinal no fechamento, ordens limitadas na abertura seguinte. Custos da configuração e estresse 2x.',
              'Política atual: ao atingir drawdown de 15%, bloqueia ordens; posições remanescentes ainda variam.',
              'Mínimas diárias simultâneas: estimativa conservadora de risco, sem inferir uma sequência intradiária.',
              'Benchmark: compra inicial 50/50, incluindo custos de entrada e saída estimados.',
              'Aprovação histórica exige todas as janelas, cenário contínuo, estresse e posições iniciais.',
              'Mesmo uma qualificação histórica não equivale a aprovação independente. JSON contém todas as tentativas.',
              '', 'Consulta UTC: ' + report['created'], 'Código: `' + report['code_hash'] + '`.']
    output.with_suffix('.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
