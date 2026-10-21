"""One deterministic OFFLINE fixture cycle; no API calls or broker access."""
import argparse
import hashlib
import json
from pathlib import Path
from ai_shadow.state import snapshot
from ai_shadow.collector import ReplayCollector
from ai_shadow.journal import Journal
from ai_shadow.risk import assess
from ai_shadow.policy import judge
from ai_shadow.jev_client import FixtureClient,CircuitBreaker
from ai_shadow.review import review

ROOT=Path(__file__).resolve().parent


def run(folder,stop=False):
    plan=ROOT/'experiments/ai_shadow_plan.json'
    plan_hash=hashlib.sha256(plan.read_bytes()).hexdigest()
    sources=sorted((ROOT/'ai_shadow').glob('*.py'))+[Path(__file__).resolve()]
    code_hash=hashlib.sha256(b''.join(p.read_bytes() for p in sources)).hexdigest()
    book=dict(symbol='BTCUSDT',bid=100.,ask=100.01,bid_qty=3.,ask_qty=1.,received_at=4000,event_at=3999,sequence=5,continuous=True)
    history=[dict(time=4000-(60-i)*60,received_at=4000-(60-i)*60,close=100+i*.001) for i in range(61)]
    account=dict(equity=20.,cash=20.,positions=0,inventory_fraction=0.)
    collector=ReplayCollector();collector.accept(book)
    state=snapshot(collector.latest(4000),history,account,4000)
    fixture=dict(regime='trending',direction='long',probabilities={'long':.94,'short':.03,'neutral':.03},confidence=.91,
                 toxic_flow=False,setup_quality=2.5,risk_state='safe',model='fixture-v1',schema='shadow-v1')
    identity=hashlib.sha256((plan_hash+'BTCUSDT4000shadow-v1').encode()).hexdigest()
    journal=Journal(Path(folder)/'session.sqlite',plan_hash,code_hash)
    try:
        previous=journal.request(identity)
        if previous:
            return dict(mode='OFFLINE_FIXTURE',replayed=False,duplicate=True,previous_phase=previous['phase'],trading_enabled=False,
                        note='Mesmo evento não é avaliado novamente. Nenhuma API ou ordem.')
        risk=assess(journal,account,4000,stop=stop)
        state.update(drawdown=risk['drawdown'],daily_loss=risk['daily_loss'],risk_gate=risk['reason'])
        journal.reserve(identity,dict(snapshot=state,book=book,history=history,account=account),0)
        circuit=CircuitBreaker(journal)
        if not circuit.allowed(4000):raise ValueError('Circuito aberto')
        response=FixtureClient(fixture).evaluate(state)
        circuit.success(4000)
        result=judge(response,risk,journal=journal)
        journal.finish(identity,dict(response=response,decision=result))
        report=dict(mode='OFFLINE_FIXTURE',synthetic_prices=True,synthetic_account=True,synthetic_response=True,
                    decision_id=identity,decision=result,state=state,review=review([]),
                    requests_paid=0,orders=0,trading_enabled=False,provider_enabled=False,
                    note='Demonstração de software; não mede retorno, edge, calibração ou latência Jev.')
        Path(folder,'demo-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        return report
    finally:journal.close()


def main():
    parser=argparse.ArgumentParser(description='Demonstração offline com dados artificiais; não inicia bot ao vivo.')
    parser.add_argument('--paper',action='store_true');parser.add_argument('--observe-only',action='store_true')
    args=parser.parse_args()
    if not(args.paper and args.observe_only):parser.error('Exige --paper --observe-only; nenhum modo real implementado')
    try:report=run(ROOT/'reports/local/ai-shadow-offline',stop=(ROOT/'STOP').exists())
    except (ValueError,OSError) as error:raise SystemExit('Demonstração bloqueada: '+str(error)) from None
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
