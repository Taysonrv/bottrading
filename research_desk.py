"""Saved evidence -> fixed-rule evaluation -> brief. No scheduler or order adapter.

Known inspected data is ALWAYS exploratory. No automatic strategy promotion.
"""
import argparse
from dataclasses import asdict
from datetime import datetime,timezone
from decimal import Decimal as D
import hashlib
import json
import math
from pathlib import Path
import time
import uuid
from spot_engine.main import save
from spot_engine.data import load_history
from spot_engine.risk import Rules
from session_performance import load as performance
from system_status import read

ROOT=Path(__file__).resolve().parent
SOURCES=(('ema15_rolling','EMA/ATR 15m — janelas móveis','rolling-20261024-summary.json'),
         ('ema_single_exit','EMA20/50 1h — saída única','single-exit-20261025.json'),
         ('pullback_single_exit','Pullback alinhado 1h — saída única','pullback-20-20261029.json'))


def finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def evaluate_saved(key,title,report):
    """Reject unknown schemas; never reinterpret observed data as untouched OOS."""
    checks=[];metrics={};schema=False
    def check(name,passed):checks.append(dict(check=name,passed=passed is True))
    if key in ('ema_single_exit','pullback_single_exit'):
        scope='SINGLE_EXIT_FIXED_HYPOTHESIS_RESEARCH' if key=='ema_single_exit' else 'PULLBACK_20_EXPLORATORY_RESEARCH'
        schema=report.get('scope')==scope and report.get('policy',{}).get('capital')=='20'
        scenarios=report.get('scenarios',[])
        bases=[s for s in scenarios if s.get('name')=='base'];stresses=[s for s in scenarios if s.get('name')=='double_costs']
        if schema and len(bases)==len(stresses)==1:
            base=bases[0].get('continuous',{});stress=stresses[0].get('continuous',{});windows=bases[0].get('windows',[])
            metrics={k:base.get(k) for k in ('net_return','closed_trades','win_rate','profit_factor','max_drawdown','sharpe_zero_rf','buy_hold_return','fees')}
            metrics['stress_return']=stress.get('net_return')
            check('NET_POSITIVE_AFTER_COSTS',finite(base.get('net_return')) and base['net_return']>0)
            check('AT_LEAST_30_CLOSED_CYCLES',type(base.get('closed_trades')) is int and base['closed_trades']>=30)
            check('DD_AT_MOST_10_PERCENT',finite(base.get('max_drawdown')) and 0<=base['max_drawdown']<=.10)
            check('AT_LEAST_THREE_POSITIVE_BLOCKS',len(windows)==4 and sum(finite(w.get('net_return')) and w['net_return']>0 for w in windows)>=3)
            check('POSITIVE_DOUBLE_COST_STRESS',finite(stress.get('net_return')) and stress['net_return']>0)
            check('BEATS_BUY_AND_HOLD',finite(base.get('net_return')) and finite(base.get('buy_hold_return')) and base['net_return']>base['buy_hold_return'])
            observations=[x for scenario in (bases[0],stresses[0]) for x in [scenario.get('continuous',{}),*scenario.get('windows',[])]]
            check('NO_BLOCKED_OR_OPEN_EXITS',all(x.get('position_open') is False and x.get('blocked_exit_attempts')==0 and x.get('drawdown_latched') is False for x in observations))
            try:costs=all(D(str(base.get(k)))==D('.001') and D(str(stress.get(k)))==D('.002') for k in ('fee_rate','slippage_rate'))
            except ArithmeticError:costs=False
            check('COST_PARAMETERS_ENFORCED',costs)
        else:schema=False
    elif key=='ema15_rolling':
        schema=report.get('scope')=='EXISTING_EMA_ATR_NOT_V3_BACKTEST'
        rows=[s for s in report.get('scenarios',[]) if s.get('scenario')=='base']
        metrics=dict(rolling_windows=rows[0].get('windows'),passing_windows=rows[0].get('passing_phase1')) if len(rows)==1 else {}
        check('ROLLING_WINDOWS_PASS',len(rows)==1 and type(rows[0].get('windows')) is int and rows[0]['windows']>0 and rows[0].get('passing_phase1')==rows[0]['windows'])
    check('SUPPORTED_RECONCILABLE_SCHEMA',schema)
    # This registry imports known previously inspected samples. A boolean in a
    # source report cannot turn those samples into independent validation.
    check('UNTOUCHED_OOS_EVIDENCE',False)
    return dict(id=key,title=title,status='REJECTED' if any(not c['passed'] for c in checks if c['check']!='UNTOUCHED_OOS_EVIDENCE') else 'EXPLORATORY_ONLY',
        metrics=metrics,checks=checks,score_25=None,independent_oos=False,
        approved=False,execution_authorized=False,
        why_this_could_fail=['Known previously inspected data; selection and multiple-testing bias remain.',
            'Hypothetical costs, static filters, gaps and liquidity may invalidate fills.',
            'No evidence here of repeatability across untouched periods or market regimes.'])


def brief(report):
    lines=['# Resumo da pesquisa — PAPER / sem promoção',
        'Gerado UTC: '+report['generated_utc'],
        'Fontes: evidências salvas e histórico público já inspecionado; sem coleta de notícias ou X nesta rotina.',
        'Nenhum preço ou contexto antigo é apresentado como mercado ao vivo.',
        'Estratégias aprovadas: 0. Ranking de vencedoras: indisponível.',
        'Score fora da amostra: não calculado sem evidência independente.','']
    for item in report['evaluations']:
        lines+=['## '+item['title'], 'Estado: '+item['status'],
            'Métricas da amostra: '+json.dumps(item['metrics'],ensure_ascii=False,allow_nan=False),
            'Critérios não atendidos: '+', '.join(c['check'] for c in item['checks'] if not c['passed']),
            'WHY THIS COULD FAIL: '+' '.join(item['why_this_could_fail']),'']
    s=report['paper_session']
    lines+=['## Sessão PAPER observada',
        'Estado: '+str(s.get('phase','UNKNOWN'))+'; ciclos: '+str(s.get('closed_cycles','UNKNOWN')),
        'Patrimônio: '+str(s.get('equity'))+' USDT; realizado: '+str(s.get('realized'))+' USDT.',
        '## Próximo passo',
        'Registrar nova hipótese e protocolo antes de olhar os resultados em dados futuros separados.',
        'Não gerar ou ativar um robô vencedor quando nenhuma hipótese sobreviveu.',
        'Sem agenda automática, conta conectada, IA paga, envio externo ou alteração de carteira.']
    return '\n'.join(lines)+'\n'


def run(root,csv_path=None):
    root=Path(root);run_id=uuid.uuid4().hex;folder=root/'reports/local/research-desk'/run_id
    folder.mkdir(parents=True,exist_ok=False)
    plan=json.loads((ROOT/'experiments/research_desk_plan.json').read_text(encoding='utf-8'))
    inputs={};provenance=[]
    for key,title,name in SOURCES:
        path=ROOT/'research_results'/name;raw=path.read_bytes()
        inputs[key]=json.loads(raw.decode('utf-8-sig'))
        provenance.append(dict(id=key,file=name,sha256=hashlib.sha256(raw).hexdigest(),evidence_updated_ms=inputs[key].get('updated_ms'),timestamp_utc=inputs[key].get('timestamp_utc')))
    manifest=dict(run_id=run_id,started_ms=int(time.time()*1000),protocol=plan,
        mode='REPLAY_KNOWN_DATA' if csv_path else 'IMPORT_SAVED_EVIDENCE',inputs=provenance,
        retrospective=True,new_strategy_variants=0,execution_authorized=False,
        source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
            ('research_desk.py','experiments/research_desk_plan.json','single_exit_research.py','pullback_research.py','spot_engine/strategy.py','spot_engine/config.py','spot_engine/risk.py','spot_engine/data.py')})
    save(folder/'manifest.json',manifest)  # Persist protocol before any replay.
    replay_artifacts=[]
    if csv_path:
        raw=Path(csv_path).read_bytes();baseline=inputs['ema_single_exit']
        if hashlib.sha256(raw).hexdigest()!=baseline['csv_sha256']:raise ValueError('KNOWN_EXPLORATORY_CSV_REQUIRED')
        from single_exit_research import evaluate
        from pullback_research import pullback_signals
        h=load_history(csv_path);r=baseline['filter_assumptions']
        rules=Rules(**{k:v if k in ('symbol','observed_ms') else D(v) for k,v in r.items()})
        for key,generator in [('ema_single_exit',None),('pullback_single_exit',pullback_signals)]:
            result=evaluate(h,rules,signal_generator=generator)
            if generator:result['scope']='PULLBACK_20_EXPLORATORY_RESEARCH'
            result['csv_sha256']=baseline['csv_sha256'];save(folder/(key+'.json'),result);inputs[key]=result
            replay_artifacts.append(dict(file=key+'.json',sha256=hashlib.sha256((folder/(key+'.json')).read_bytes()).hexdigest()))
    evaluations=[evaluate_saved(key,title,inputs[key]) for key,title,_ in SOURCES]
    now=int(time.time()*1000)
    report=dict(scope='RESEARCH_DESK_FIXED_EVIDENCE',run_id=run_id,updated_ms=now,
        generated_utc=datetime.fromtimestamp(now/1000,timezone.utc).isoformat(),mode=manifest['mode'],
        evaluations=evaluations,approved_strategies=[],winner=None,builder_status='BLOCKED_NO_VALIDATED_STRATEGY',
        source_provenance=provenance,replay_artifacts=replay_artifacts,source_hashes=manifest['source_hashes'],paper_session=performance(root,now),
        market_context=dict(saved_radar_updated_ms=read(root/'reports/local/portfolio/radar.json').get('updated_ms'),
                            live_market_claim=False),
        scheduled=False,external_messages_sent=0,paid_model_calls=0,execution_authorized=False,approved=False)
    report['brief']=brief(report);save(folder/'report.json',report)
    (folder/'brief.md').write_text(report['brief'],encoding='utf-8')
    save(root/'reports/local/research-desk/latest.json',report)
    return report


def main():
    p=argparse.ArgumentParser(description='Fluxo integrado de evidência, avaliação e resumo; sem trading ou agenda.')
    p.add_argument('--data-dir',type=Path,required=True);p.add_argument('--replay-csv',type=Path)
    args=p.parse_args();report=run(args.data_dir,args.replay_csv)
    print(json.dumps(dict(run_id=report['run_id'],mode=report['mode'],evaluated=len(report['evaluations']),approved=0,builder=report['builder_status']),ensure_ascii=False))


if __name__=='__main__':main()
