"""Close-confirmed inventory grid experiment, not exchange resting limit orders."""
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import statistics
import time
import urllib.request
import research

LEVELS = 8
LOOKBACK = 168
COOLDOWN = 24


def schedule(rows, config, hybrid=False):
    """Frozen band per episode; decisions at i use bars strictly before i."""
    research.check_rows(rows)
    targets, decisions = [], []
    band, wait_until, episodes, breaks = None, 0, 0, 0
    # Require each step to exceed estimated round-trip costs by a factor of two.
    minimum_step = 4 * (config['fee_rate'] + config['slippage_rate'])
    for i in range(len(rows)):
        fraction, mode = 0., 'aquecimento'
        if i >= 200:
            previous = rows[i-1]['close']
            recent = [r['close'] for r in rows[i-25:i]]
            moves = [b/a-1 for a, b in zip(recent, recent[1:])]
            crash = previous / recent[0] - 1 <= -.06
            nervous = statistics.pstdev(moves) >= .018
            fast = statistics.mean(r['close'] for r in rows[i-24:i])
            slow = statistics.mean(r['close'] for r in rows[i-168:i])
            lateral = abs(fast/slow-1) < .01
            if band and (previous < band[0] or previous > band[1] or crash or nervous):
                band, wait_until = None, i + COOLDOWN
                breaks += 1
            mode = 'caixa'
            if i < wait_until or crash or nervous:
                mode = 'proteção'
            else:
                if band is None and lateral:
                    lower = min(r['low'] for r in rows[i-LOOKBACK:i])
                    upper = max(r['high'] for r in rows[i-LOOKBACK:i])
                    step = (upper-lower)/LEVELS
                    if step/upper >= minimum_step:
                        band = (lower, upper)
                        episodes += 1
                if band:
                    lower, upper = band
                    step = (upper-lower)/LEVELS
                    # Fixed ladder; larger inventory at lower levels, never beyond budget.
                    fraction = max(0., min(1., math.floor((upper-previous)/step)/LEVELS))
                    mode = 'grid'
                elif hybrid and not lateral and previous > fast > slow:
                    fraction, mode = 1., 'tendência'
            if band:
                decisions.append({'index': i, 'mode': mode, 'lower': band[0], 'upper': band[1]})
        targets.append(fraction)
    return targets, {'episodes': episodes, 'breaks': breaks, 'bands': decisions}


def evaluate(histories, config):
    stamps = [r['open_time'] for r in next(iter(histories.values()))]
    if len(stamps) < 200 + 180*24:
        raise ValueError('Exige pelo menos 180 dias de avaliação e aquecimento')
    for rows in histories.values():
        research.check_rows(rows)
        if [r['open_time'] for r in rows] != stamps:
            raise ValueError('Históricos desalinhados')
    end = len(stamps)
    boundary = 200 + (end-200)*3//4
    width = (boundary-200)//3
    windows = {f'fold_{j+1}': (200+j*width, boundary if j == 2 else 200+(j+1)*width)
               for j in range(3)}
    windows.update(final_reused=(boundary, end), continuous=(200, end))
    results = {}
    for hybrid in (False, True):
        schedules = {s: schedule(rows, config, hybrid) for s, rows in histories.items()}
        def target(symbol, i):
            return schedules[symbol][0][i]
        def run(a, b, **kwargs):
            return research.backtest(histories, a, b, config, 'grid_research', None,
                                     target_at=target, **kwargs)
        scenarios = {name: run(*window) for name, window in windows.items()}
        scenarios['stress'] = run(boundary, end, stress=2)
        scenarios['existing'] = run(boundary, end, initial_exposure=.8)
        scenarios['reduce_experimental'] = run(200, end, risk_policy='reduce')
        # Qualification retains the engine's gates, including every scenario.
        passed = all(r['passed'] for r in scenarios.values())
        results['grid_hybrid_v1' if hybrid else 'grid_range_v1'] = {
            'scenarios': scenarios, 'qualified_historical': passed,
            'episodes': {s: data[1]['episodes'] for s, data in schedules.items()},
            'breaks': {s: data[1]['breaks'] for s, data in schedules.items()}}
    return results


def main():
    root = Path(__file__).resolve().parent
    config = json.loads((root/'config.json').read_text(encoding='utf-8'))
    def request(url):
        with urllib.request.urlopen(url, timeout=30) as response:
            return json.load(response)
    cutoff = int(time.time()*1000)//research.HOUR*research.HOUR
    histories = {s: research.download(s, 365, request, end=cutoff) for s in ('BTCUSDT', 'ETHUSDT')}
    report = {'created': dt.datetime.now(dt.timezone.utc).isoformat(), 'adopted': False,
              'independent_out_of_sample': False, 'config': config,
              'parameters': dict(levels=LEVELS, lookback_hours=LOOKBACK, cooldown_hours=COOLDOWN,
                                 minimum_step=4*(config['fee_rate']+config['slippage_rate'])),
              'code_hash': hashlib.sha256(b''.join((root/name).read_bytes() for name in
                           ('grid_research.py', 'research.py', 'execution.py'))).hexdigest(),
              'data_hash': hashlib.sha256(json.dumps(histories, sort_keys=True).encode()).hexdigest(),
              'comparisons': evaluate(histories, config)}
    output = root/'reports/2026-10-18-grid-results.json'
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    lines = ['# Grid por inventário — pesquisa histórica', '',
             'Simulação com sinais no fechamento e execução na abertura seguinte, não reprodução do Grid nativo da Binance.',
             'Histórico de 365 dias já consultado: desenvolvimento, sem confirmação independente. Nenhuma adoção.', '',
             '| Hipótese | Cenário | Retorno | Comprar e manter | Drawdown | Ordens | Custos USDT | Passou cenário |',
             '|---|---|---:|---:|---:|---:|---:|---|']
    for name, result in report['comparisons'].items():
        if name == 'grid_hybrid_v1':
            lines += ['| Hipótese | Cenário | Retorno | Comprar e manter | Drawdown | Ordens | Custos USDT | Passou cenário |',
                      '|---|---|---:|---:|---:|---:|---:|---|']
        for scenario, r in result['scenarios'].items():
            lines.append(f"| {name} | {scenario} | {r['return']:.2%} | {r['benchmark']:.2%} | {r['drawdown']:.2%} | {r['trades']} | {r['costs_usdt']:.2f} | {'Sim' if r['passed'] else 'Não'} |")
        lines += ['', f"{name}: qualificação histórica = {result['qualified_historical']}; episódios = {result['episodes']}; rupturas/proteções = {result['breaks']}.", '']
    lines += ['Inclui taxas, slippage e marcação de todas as posições. Não simula fila, liquidez, fills intradiários ou spread separado do slippage.',
              'Faixa fixa por episódio com oito degraus; filtro lateral por médias 24/168h; intervalo mínimo por degrau = quatro vezes taxa + slippage.',
              'Ruptura detectada no fechamento encerra o episódio e solicita alvo zero, sujeito aos limites de venda. Carência de 24h antes de novo episódio.',
              'Híbrido usa tendência somente sem episódio de grid e fora da carência; pode errar a classificação. Não usa DCA nem martingale.',
              'STOP do simulador prevalece. Ao gatilho de 15%, o cenário normal congela ordens e mantém posições; reduce_experimental só vende gradualmente.',
              'As mínimas horárias simultâneas são uma aproximação conservadora de risco. O gatilho não garante perda máxima de 15%.',
              'Desenvolvimento em três janelas anteriores ao período final (25%), além de carteira contínua, custos 2x e posições iniciais de 80%.',
              'Pesquisa usa BTC/ETH em carteira conjunta; não inclui validações individuais por ativo. Nenhum resultado altera validation.json.',
              '', 'Consulta UTC: '+report['created'], 'Código: `'+report['code_hash']+'`.']
    output.with_suffix('.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
