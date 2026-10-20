"""One terminal for the paper experiment, public stream and local dashboard."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
from paper_lab import lock
from runtime_status import status

ROOT = Path(__file__).resolve().parent


def preflight(root, port):
    if (root / 'STOP').exists():
        raise ValueError('STOP acionado. Revise antes de remover com python bot.py resume.')
    path = root / 'reports/local/live-small-paper.json'
    if path.exists():
        state = json.loads(path.read_text(encoding='utf-8'))
        if state.get('end', 0) <= time.time():
            raise ValueError('Sessão de 20 USDT encerrada. Preserve e revise o relatório; saldo não será reiniciado.')
        if state.get('halted'):
            raise ValueError('Drawdown travado; exige revisão. Saldo não será reiniciado.')
    if (root / 'reports/local/market-stream.lock').exists():
        raise ValueError('Coletor já iniciado ou trava pendente. Confira o processo; não remova a trava enquanto estiver ativo.')
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', port))
        except OSError:
            raise ValueError(f'Porta {port} ocupada. Encerre o painel antigo ou escolha --port outra_porta.') from None
    node = shutil.which('node')
    if not node:
        raise ValueError('Instale Node.js 24 ou superior para o coletor público.')
    major = int(subprocess.check_output([node, '--version'], text=True).strip().lstrip('v').split('.')[0])
    if major < 24:
        raise ValueError('O coletor requer Node.js 24 ou superior.')
    return node


def main():
    parser = argparse.ArgumentParser(description='Somente simulação Spot de 20 USDT; sem ordens reais.')
    parser.add_argument('--port', type=int, default=8768)
    parser.add_argument('--check', action='store_true', help='Verifica requisitos sem iniciar processos')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Porta entre 1024 e 65535')
    folder = ROOT / 'reports/local'
    folder.mkdir(parents=True, exist_ok=True)
    children = []
    try:
        with lock(folder / 'launcher.lock'), ExitStack() as files:
            node = preflight(ROOT, args.port)
            # OS lock detects another paper process without trusting a stale PID.
            with lock(folder / 'live-small-paper.lock'):
                pass
            if args.check:
                print('Requisitos disponíveis. Nenhum processo iniciado.')
                return
            environment = os.environ.copy()
            environment.setdefault('SPOTLAB_ACCESS_CODE', secrets.token_urlsafe(18))
            commands = [
                ('paper', [sys.executable, '-u', 'live_small_paper.py', '--hours', '24']),
                ('stream', [node, 'market_stream.js']),
                ('panel', [sys.executable, '-u', 'dashboard.py', '--port', str(args.port)])]
            try:
                for name, command in commands:
                    output = files.enter_context((folder / f'launcher-{name}.log').open('a', encoding='utf-8'))
                    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
                    child = subprocess.Popen(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, creationflags=flags, env=environment)
                    children.append((name, child))
                print(f'Painel: http://127.0.0.1:{args.port}/', flush=True)
                print('Código de acesso: ' + environment['SPOTLAB_ACCESS_CODE'], flush=True)
                print('20 USDT fictícios. Ctrl+C encerra os três processos iniciados aqui. Não feche este terminal.', flush=True)
                previous_status = None
                next_summary = 0.0
                while True:
                    for name, child in children:
                        if child.poll() is not None:
                            raise RuntimeError(f'{name} encerrou (código {child.returncode}). Confira reports/local/launcher-{name}.log. Outros componentes serão encerrados.')
                    current_status, summary = status(ROOT)
                    if current_status != previous_status or time.monotonic() >= next_summary:
                        print(summary, flush=True)
                        previous_status = current_status
                        next_summary = time.monotonic() + 300
                    time.sleep(1)
            except KeyboardInterrupt:
                print('Encerrando os componentes; carteira fictícia preservada.')
            finally:
                for _, child in reversed(children):
                    if child.poll() is None:
                        child.terminate()
                for _, child in children:
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        child.kill(); child.wait()
                stream_pid = next((child.pid for name, child in children if name == 'stream'), None)
                stream_lock = folder / 'market-stream.lock'
                if stream_pid and stream_lock.exists() and stream_lock.read_text().strip() == str(stream_pid):
                    stream_lock.unlink()
    except (ValueError, RuntimeError, OSError) as error:
        raise SystemExit(str(error)) from None


if __name__ == '__main__':
    main()
