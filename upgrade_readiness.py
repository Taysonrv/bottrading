"""Advisory transition checklist, never an execution authorization or migration."""
import argparse
from pathlib import Path
import time
from portfolio_alerts import ledger
from portfolio12 import SYMBOLS
from spot_engine.main import save
from system_status import read


def build(current,next_root,now_ms=None):
    current=Path(current);next_root=Path(next_root);now=int(time.time()*1000) if now_ms is None else now_ms
    plan=read(current/'reports/local/portfolio/plan.json');costs=read(current/'reports/local/paper12-feasibility/latest.json')
    checks=[]
    def add(key,passed,reason):checks.append(dict(check=key,passed=passed,reason=reason))
    try:s=ledger(current)
    except Exception:s=None
    add('CURRENT_LEDGER',s is not None,'Ledger atual reconciliado' if s is not None else 'Ledger não confirmado')
    end=plan.get('end_ms');add('CURRENT_SESSION_ENDED',type(end) is int and now>=end,'Não abrir outra carteira em paralelo')
    add('NO_REMAINING_EXPOSURE',s is not None and not s['position'] and not s['pending'],'Revisar inventário e reservas antes da transição')
    add('CURRENT_RISK_CLEAR',s is not None and not s['halt'],'Não usar nova sessão para contornar uma trava de risco')
    marker=read(next_root/'portfolio12.json')
    add('NEXT_PROFILE12',marker=={'variant':'PAPER12_V1'},'Perfil12 explícito, sem migração')
    add('SEPARATE_ROOT',current.resolve()!=next_root.resolve(),'Experimentos devem ter raízes diferentes')
    add('NEXT_WALLET_NOT_ISSUED',not (next_root/'reports/local/portfolio/paper.sqlite').exists(),'Não reiniciar saldo ou reinterpretar ledger existente')
    add('NEXT_STOP_CLEAR',not (next_root/'STOP').exists() and not (next_root/'reports/local/portfolio/STOP').exists(),'STOP nunca removido automaticamente')
    stamp=costs.get('updated_ms');fresh=type(stamp) is int and 0<=now-stamp<=1800000
    rows=costs.get('pairs',[])
    add('FRESH_MECHANICAL_SCREEN',fresh and len(rows)==12 and {r.get('symbol') for r in rows}==set(SYMBOLS) and all(r.get('mechanically_feasible') is not None for r in rows),'Amostra pública completa de até30min; não é sinal nem validação')
    add('SOME_MECHANICALLY_FEASIBLE_PAIRS',any(r.get('mechanically_feasible') is True for r in rows),'Viabilidade mecânica não demonstra vantagem')
    return dict(scope='PAPER12_TRANSITION_ADVISORY',updated_ms=now,current_name=current.name,next_name=next_root.name,
        ready_for_operator_review=all(c['passed'] for c in checks),checks=checks,execution_authorized=False,approved=False,
        note='Advisory only. A completed checklist cannot establish edge, automatically start a wallet or authorize real money.')


def main():
    p=argparse.ArgumentParser();p.add_argument('--current',type=Path,required=True);p.add_argument('--next',type=Path,required=True)
    args=p.parse_args();report=build(args.current,args.next)
    folder=args.current/'reports/local/upgrade-readiness';folder.mkdir(parents=True,exist_ok=True)
    save(folder/'latest.json',report)
    for row in report['checks']:print(('OK ' if row['passed'] else 'PENDENTE ')+row['check'])
    print('Ordens autorizadas: não. Checklist não inicia execução.')


if __name__=='__main__':main()
