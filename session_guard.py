"""External bounded UI guardian. Never launches the trading engine or resets state."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from spot_engine.main import single_runner,save
from supervisor_health import event
from system_status import read

ROOT=Path(__file__).resolve().parent


def decision(plan,status,control,*,now_ms,stop,port_open,attempts):
    end=plan.get('end_ms')
    if type(end) is not int or type(plan.get('start_ms')) is not int or not plan['start_ms']<end:
        return 'INVALID_PLAN'
    if stop:return 'STOP'
    if now_ms>=end:return 'DEADLINE'
    stamps=[r.get('updated_ms') for r in (status,control)]
    if any(type(s) is int and s>now_ms for s in stamps):return 'CLOCK_UNVERIFIED'
    cs=control.get('updated_ms');es=status.get('updated_ms')
    controller_fresh=type(cs) is int and now_ms-cs<30000 and control.get('phase') in ('RUNNING','DEGRADED')
    engine_fresh=type(es) is int and now_ms-es<60000 and status.get('phase')=='RUNNING'
    if controller_fresh:return 'SUPERVISOR_HANDLES_RECOVERY'
    if not port_open and attempts<3:return 'RESTORE_PANEL_ONLY'
    if not engine_fresh:return 'ENGINE_REQUIRES_REVIEW'
    return 'SUPERVISOR_REQUIRES_REVIEW'


def listening(port):
    with socket.socket() as sock:
        sock.settimeout(1)
        return sock.connect_ex(('127.0.0.1',port))==0


def cycle(root,port):
    folder=root/'reports/local';path=folder/'external-guard.json'
    previous=read(path);attempts=previous.get('panel_recovery_attempts',0)
    if type(attempts) is not int or not 0<=attempts<=3:raise ValueError('GUARD_STATE_INVALID')
    plan=read(folder/'portfolio/plan.json');status=read(folder/'portfolio/status.json');control=read(folder/'system-run.json')
    now=int(time.time()*1000)
    action=decision(plan,status,control,now_ms=now,
        stop=(root/'STOP').exists() or (folder/'portfolio/STOP').exists(),port_open=listening(port),attempts=attempts)
    report=dict(updated_ms=now,state=action,panel_recovery_attempts=attempts,
        end_ms=plan.get('end_ms'),engine_auto_restart=False,real_orders=0,
        note='External Windows task; panel-only recovery. Engine failure requires review; no cash/deadline/STOP changes.')
    if action=='RESTORE_PANEL_ONLY':
        # Persist the attempt BEFORE spawning; a crash cannot erase the retry budget.
        attempts+=1;report['panel_recovery_attempts']=attempts;save(path,report)
        event(root,'EXTERNAL_PANEL_RECOVERY',component='dashboard',attempt=attempts,reason='SUPERVISOR_UNCONFIRMED')
        with (folder/'external-panel.log').open('a',encoding='utf-8') as log:
            flags=subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0
            child=subprocess.Popen([sys.executable,'-u',str(ROOT/'dashboard.py'),'--data-dir',str(root),'--port',str(port)],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=flags)
        report['panel_pid']=child.pid
    if action!=previous.get('state'):
        event(root,'EXTERNAL_GUARD_STATE',component='external_guard',reason=action)
    save(path,report)
    return report


def main():
    p=argparse.ArgumentParser(description='Guardião externo limitado ao prazo existente; nunca reinicia o motor.')
    p.add_argument('--data-dir',type=Path,required=True);p.add_argument('--port',type=int,default=8769)
    p.add_argument('--watch',action='store_true');args=p.parse_args()
    if not 1024<=args.port<=65535:p.error('Porta inválida.')
    root=args.data_dir.resolve();folder=root/'reports/local'
    if not (folder/'portfolio/plan.json').is_file():p.error('Sessão existente obrigatória.')
    with single_runner(folder/'external-guard.lock'):
        while True:
            report=cycle(root,args.port)
            print(json.dumps(report),flush=True)
            if not args.watch or report['state'] in ('STOP','DEADLINE','INVALID_PLAN','CLOCK_UNVERIFIED'):break
            time.sleep(30)


if __name__=='__main__':main()
