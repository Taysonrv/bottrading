"""Explicit bounded research/control daemon; not a trading process."""
import argparse
import os
import secrets
import threading
from pathlib import Path
import time
from spot_engine.main import single_runner
from quant_control.service import Control


def main():
    p=argparse.ArgumentParser(description='Controle quantitativo público; sem IA paga ou ordens.')
    p.add_argument('--data-dir',type=Path,required=True);p.add_argument('--hours',type=int,default=24)
    p.add_argument('--once',action='store_true')
    p.add_argument('--with-panel',action='store_true',help='Painel local e controle em um processo, sem motor de ordens.')
    p.add_argument('--port',type=int,default=8768);args=p.parse_args()
    if not 1<=args.hours<=48:p.error('Duração de1 a48 horas.')
    if not 1024<=args.port<=65535:p.error('Porta inválida.')
    with single_runner(args.data_dir/'reports/local/quant-control/runner.lock'):
        server=None;control=None
        try:
            if args.with_panel:
                from dashboard import DashboardServer
                code=os.getenv('SPOTLAB_ACCESS_CODE') or secrets.token_urlsafe(18)
                if len(code)<12:raise ValueError('LOCAL_ACCESS_CODE_TOO_SHORT')
                server=DashboardServer(('127.0.0.1',args.port),args.data_dir.resolve(),code,
                    {f'localhost:{args.port}',f'127.0.0.1:{args.port}'})
                threading.Thread(target=server.serve_forever,daemon=True,name='quant-dashboard').start()
                print(f'Painel: http://127.0.0.1:{args.port}/#v3',flush=True)
                print('Código de acesso: '+code,flush=True)
            control=Control(args.data_dir);deadline=time.monotonic()+args.hours*3600
            while time.monotonic()<deadline and not control.stopped():
                try:control.cycle()
                except Exception:control.publish([],False,'CONTROL_UNAVAILABLE',time.monotonic())
                if args.once:break
                for _ in range(30):
                    if control.stopped():break
                    time.sleep(1)
        finally:
            if control is not None:
                try:control.publish([],False,'STOP' if control.stopped() else 'ENDED',time.monotonic())
                finally:control.close()
            if server is not None:server.shutdown();server.server_close()


if __name__=='__main__':main()
