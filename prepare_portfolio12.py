"""Prepare a NEW paper root; never modifies an existing experiment or starts orders."""
import argparse
import json
from pathlib import Path
import shutil


def prepare(root):
    root=Path(root)
    root.mkdir(parents=True,exist_ok=False)
    source=Path(__file__).resolve().parent
    (root/'spot_engine').mkdir()
    for name in ('main.py','config.py'):
        shutil.copyfile(source/'spot_engine'/name,root/'spot_engine'/name)
    (root/'portfolio12.json').write_text(json.dumps({'variant':'PAPER12_V1'}),encoding='utf-8')
    return root


def main():
    p=argparse.ArgumentParser(description='Prepara raiz NOVA de ensaio12; não inicia execução.')
    p.add_argument('--data-dir',type=Path,required=True);args=p.parse_args()
    root=prepare(args.data_dir)
    print('Perfil12 preparado, sem carteira emitida ou motor iniciado: '+str(root.resolve()))


if __name__=='__main__':main()
