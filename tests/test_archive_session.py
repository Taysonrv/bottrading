import importlib.util
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('archive_session',Path(__file__).resolve().parents[1]/'scripts/archive_session.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)


class ArchiveTests(unittest.TestCase):
    def setup_session(self,root,units='0'):
        folder=Path(root)/'reports/local/spot-runs/ema20'
        dbfolder=folder/'reports/local/spot-execution';dbfolder.mkdir(parents=True)
        (folder/'session.json').write_text(json.dumps({'identity':'test-identity'}))
        (folder/'status.json').write_text(json.dumps(dict(phase='STOPPED',units=units,cash='20')))
        with closing(sqlite3.connect(dbfolder/'paper.sqlite')) as db:
            db.execute('CREATE TABLE ledger (id INTEGER PRIMARY KEY,payload TEXT)')
            db.execute('INSERT INTO ledger VALUES(1,?)',(json.dumps(dict(units=units,cash='20',active=None)),))
            db.commit()
        return folder

    def test_refuses_open_inventory_and_path_traversal(self):
        with tempfile.TemporaryDirectory() as root:
            self.setup_session(root,'1')
            with self.assertRaises(ValueError):mod.archive(root,'ema20','test',lambda _: 'sim')
            with self.assertRaises(ValueError):mod.archive(root,'../portfolio','test',lambda _: 'sim')

    def test_confirmation_and_checkpoint_moves_keep_global_stop(self):
        with tempfile.TemporaryDirectory() as root:
            folder=self.setup_session(root);Path(root,'STOP').write_text('risk halt')
            self.assertIsNone(mod.archive(root,'ema20','test',lambda _: 'não'))
            self.assertTrue((folder/'session.json').exists())
            archive=mod.archive(root,'ema20','test',lambda _: 'sim')
            self.assertTrue((archive/'reports/local/spot-execution/paper.sqlite').exists())
            self.assertEqual(Path(root,'STOP').read_text(),'risk halt')
            self.assertTrue((folder/'runner.lock').exists());self.assertFalse((folder/'session.json').exists())


if __name__=='__main__':unittest.main()
