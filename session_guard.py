"""External bounded UI guardian. Never launches the trading engine or resets state."""
import argparse
import json
import os
import re
from pathlib import Path
import socket
import subprocess
import sys
import time
from spot_engine.main import single_runner,save
from supervisor_health import event
from system_status import read

ROOT=Path(__file__).resolve().parent


def decision(plan,status,control,*,now_ms,stop,port_open,attempts,panel_missing_ms=0,planned_refresh=False):
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
    if controller_fresh and (port_open or (panel_missing_ms<120000 and not planned_refresh)):
        return 'SUPERVISOR_HANDLES_RECOVERY'
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
    now=int(time.time()*1000);port_open=listening(port)
    since=previous.get('panel_missing_since_ms')
    since=since if type(since) is int and 0<=since<=now else now
    request=read(folder/'panel-refresh.json');requested=request.get('requested_ms')
    handled=previous.get('last_handled_refresh_ms',0)
    planned=type(requested) is int and 0<=now-requested<=120000 and requested>handled
    action=decision(plan,status,control,now_ms=now,
        stop=(root/'STOP').exists() or (folder/'portfolio/STOP').exists(),port_open=port_open,attempts=attempts,
        panel_missing_ms=now-since,planned_refresh=planned)
    report=dict(updated_ms=now,state=action,panel_recovery_attempts=attempts,
        panel_missing_since_ms=None if port_open else since,last_handled_refresh_ms=handled,
        end_ms=plan.get('end_ms'),engine_auto_restart=False,real_orders=0,
        note='External Windows task; panel-only recovery. Engine failure requires review; no cash/deadline/STOP changes.')
    if action=='RESTORE_PANEL_ONLY':
        # Persist the attempt BEFORE spawning; a crash cannot erase the retry budget.
        attempts+=1;report['panel_recovery_attempts']=attempts;save(path,report)
        if planned:report['last_handled_refresh_ms']=requested;save(path,report)
        event(root,'EXTERNAL_PANEL_RECOVERY',component='dashboard',attempt=attempts,reason='PLANNED_REFRESH' if planned else 'PANEL_ENDPOINT_UNAVAILABLE')
        with (folder/'external-panel.log').open('a',encoding='utf-8') as log:
            flags=subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0
            environment=os.environ.copy()
            access=request.get('access_code') if planned else None
            if isinstance(access,str) and re.fullmatch(r'[A-Za-z0-9_-]{12,128}',access):
                environment['SPOTLAB_ACCESS_CODE']=access
            child=subprocess.Popen([sys.executable,'-u',str(ROOT/'dashboard.py'),'--data-dir',str(root),'--port',str(port)],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=flags,env=environment)
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
