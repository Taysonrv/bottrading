"""Single supervised entry point for existing PAPER components; never live.

No state reset, source migration, automatic STOP removal or deadline extension.
EMA and shared-wallet PAPER modes have separate persisted wallets.
"""
import argparse
from contextlib import ExitStack,contextmanager
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from spot_engine.main import single_runner,save
from system_status import build,read

ROOT=Path(__file__).resolve().parent


@contextmanager
def probe_existing_lock(path):
    if not path.exists():yield;return
    with path.open('r+b') as handle:
        handle.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            try:yield
            finally:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            try:yield
            finally:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


def preflight(root,port,now=None,engine='ema',execution_only=False):
    if type(port) is not int or not 1024<=port<=65535:raise ValueError('Porta inválida.')
    now=time.time() if now is None else now
    for relative in ('spot_engine/main.py','spot_engine/config.py'):
        if not (root/relative).is_file():raise ValueError('Pasta de dados precisa conter o código da sessão; não migrado automaticamente.')
    session=root/('reports/local/portfolio' if engine=='portfolio' else 'reports/local/spot-runs/ema20')
    plan_name='plan.json' if engine=='portfolio' else 'session.json'
    if (root/'STOP').exists() or (session/'STOP').exists():raise ValueError('STOP acionado; nenhuma trava removida automaticamente.')
    plan=read(session/plan_name)
    if (session/plan_name).exists() and not plan:raise ValueError('Plano da sessão ilegível; preserve para revisão.')
    if plan and (type(plan.get('end_ms')) is not int or plan['end_ms']<=now*1000):raise ValueError('Prazo da sessão encerrado. Saldo e prazo não reiniciados.')
    with probe_existing_lock(session/'runner.lock'):pass
    with probe_existing_lock(root/'reports/local/multipair.lock'):pass
    if not execution_only:
        with socket.socket() as sock:
            try:sock.bind(('127.0.0.1',port))
            except OSError:raise ValueError('Porta ocupada. Use --execution-only se o painel já estiver aberto, ou outra porta.') from None
    return session


def lifecycle(children,session):
    """A dead web UI must not terminate synthetic protection or vice versa."""
    codes={name:child.poll() for name,child in children}
    if codes.get('execution') is not None:
        last=read(session/'status.json')
        reason=last.get('reason','EXECUTION_EXIT') if codes['execution']==0 else 'EXECUTION_FAILURE'
        return 'IDLE',reason
    if any(code is not None for name,code in codes.items() if name!='execution'):
        return 'DEGRADED','COMPONENT_FAILURE'
    return 'RUNNING','ACTIVE'


def commands(root,port,engine='ema'):
    if engine=='portfolio':
        return [('execution',[sys.executable,'-u','-m','spot_engine.portfolio_run','--data-dir',str(root),'--start'],ROOT),
                ('dashboard',[sys.executable,'-u',str(ROOT/'dashboard.py'),'--port',str(port),'--data-dir',str(root)],ROOT)]
    return [('execution',[sys.executable,'-u','-m','spot_engine.main','paper','--session','ema20','--hours','24','--order-budget','6'],root),
            ('market',[sys.executable,'-u','-m','spot_engine.scanner','--timeframe','15m','--output',str(root/'reports/local/multipair.json')],ROOT),
            ('dashboard',[sys.executable,'-u',str(ROOT/'dashboard.py'),'--port',str(port),'--data-dir',str(root)],ROOT)]


def main():
    parser=argparse.ArgumentParser(description='Painel + observador multipar + execução BTC/1h PAPER em um terminal.')
    parser.add_argument('--engine',choices=('ema','portfolio'),default='ema',help='portfolio: experimento separado de 20 USDT, seis pares15m.')
    parser.add_argument('--data-dir',type=Path,default=ROOT)
    parser.add_argument('--port',type=int,default=8768)
    parser.add_argument('--start',action='store_true',help='Inicia os componentes; sem esta opção apenas verifica.')
    parser.add_argument('--execution-only',action='store_true',help='Usa painel já iniciado separadamente; não ocupa sua porta nem controla seu processo.')
    args=parser.parse_args();root=args.data_dir.resolve()
    try:session=preflight(root,args.port,engine=args.engine,execution_only=args.execution_only)
    except (OSError,ValueError) as error:raise SystemExit('Não iniciado: '+str(error)) from None
    if not args.start:
        print(json.dumps(build(root),ensure_ascii=False,indent=2));print('Pré-verificação concluída. Para iniciar acrescente --start.');return
    folder=root/'reports/local';folder.mkdir(parents=True,exist_ok=True)
    children=[];reason='FAILURE';started=time.time();env=os.environ.copy()
    # Reproducible conservative defaults, no Binance credentials forwarded.
    env={k:v for k,v in env.items() if not k.startswith(('TRADING_','BINANCE_'))}
    env['SPOTLAB_ACCESS_CODE']=env.get('SPOTLAB_ACCESS_CODE') or secrets.token_urlsafe(18)
    def status(phase):
        save(folder/'system-run.json',dict(mode='PAPER',phase=phase,reason=reason,updated_ms=int(time.time()*1000),
             started_ms=int(started*1000),engine=args.engine,real_orders=0,components=[dict(name=n,pid=p.pid,exit_code=p.poll()) for n,p in children]))
    with single_runner(folder/'system.lock'),ExitStack() as stack:
        try:
            for name,command,cwd in commands(root,args.port,args.engine):
                if args.execution_only and name=='dashboard':continue
                log=stack.enter_context((folder/('system-'+name+'.log')).open('a',encoding='utf-8'))
                flags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0
                children.append((name,subprocess.Popen(command,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=flags)))
            print(f'Terminal: http://127.0.0.1:{args.port}/#terminal',flush=True)
            print('Painel externo: use o código do painel já aberto.' if args.execution_only else 'Código de acesso: '+env['SPOTLAB_ACCESS_CODE'],flush=True)
            print('PAPER: '+('carteira compartilhada de 20 USDT, seis pares15m; experimento separado da EMA.' if args.engine=='portfolio' else 'BTC/1h executa sinais; seis pares15m apenas observados.')+' Não feche este terminal.',flush=True)
            print('Ctrl+C aciona STOP local da sessão, preserva posição e encerra os componentes próprios.',flush=True)
            while True:
                phase,reason=lifecycle(children,session)
                status(phase)
                if all(child.poll() is not None for _,child in children):return
                time.sleep(1)
        except KeyboardInterrupt:reason='INTERRUPTED'
        except Exception:
            reason='SUPERVISOR_FAILURE'
            raise
        finally:
            engine=next((p for name,p in children if name=='execution'),None)
            if engine is not None and engine.poll() is None:
                # Let the engine cancel pending orders and persist STOPPED first.
                session.mkdir(parents=True,exist_ok=True)
                (session/'STOP').write_text('Unified supervisor shutdown\n',encoding='utf-8')
                try:engine.wait(timeout=25)
                except subprocess.TimeoutExpired:pass
            for _,child in reversed(children):
                if child.poll() is None:child.terminate()
            for _,child in children:
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:child.kill();child.wait()
            status('STOPPED')
            print('Encerrado: '+reason+'. Carteira preservada; STOP não vende posições.',flush=True)


if __name__=='__main__':main()
