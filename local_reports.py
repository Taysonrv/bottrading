"""Runtime reports stay outside versioned research snapshots."""
from pathlib import Path


def destination(root, filename):
    if Path(filename).name != filename or not filename.endswith('.json'):
        raise ValueError('Nome de relatório inválido')
    folder = Path(root)/'reports'/'local'
    folder.mkdir(parents=True, exist_ok=True)
    return folder/filename
