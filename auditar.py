"""Generate private evidence reports without touching the paper account."""
import json
from pathlib import Path
import threading
from paper_lab import save,lock
from session_audit import build,register
ROOT=Path(__file__).resolve().parent


def generate(root):
    folder=Path(root)/'reports/local';folder.mkdir(parents=True,exist_ok=True)
    with lock(folder/'audit.lock'):
        path=folder/'live-small-paper.json'
        state=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        result=build(state);registry=register(root)
        result['research']={'studies':len(registry['studies']),'variants':len(registry['variants']),'scope':registry['scope']}
        save(folder/'research-registry.json',registry);save(folder/'session-audit.json',result)
        lines=['# Auditoria da sessão fictícia','', 'Sem aprovação de rentabilidade. Nenhuma ordem enviada.','']
        for key in ('measurement','equity','pnl','realized','unrealized','fees','buys','sells','win_rate','profit_factor','saved_curve_drawdown','gaps_over_180s','reconciled'):
            lines.append(f'- {key}: {result.get(key)}')
        lines+=['','## Limitações','']+['- '+s for s in result.get('limits',[])]+['- '+s for s in result.get('issues',[])]
        (folder/'session-audit.md').write_text('\n'.join(lines),encoding='utf-8')
        return result


def start(root):
    stop=threading.Event()
    def work():
        if stop.wait(2):return
        while not stop.is_set():
            try:generate(root)
            except (Exception,SystemExit):print('Auditoria indisponível; execução da simulação preservada.',flush=True)
            if stop.wait(60):break
    threading.Thread(target=work,daemon=True,name='session-audit').start()
    return stop


if __name__=='__main__':
    r=generate(ROOT)
    print('Auditoria salva em reports/local/session-audit.md e .json. Reconciliação: '+str(r.get('reconciled')))
