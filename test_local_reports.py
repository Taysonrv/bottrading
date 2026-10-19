import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import limit_demo
from local_reports import destination


class LocalReportTests(unittest.TestCase):
    def test_demo_preserves_versioned_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'reports').mkdir()
            original = root/'reports/2026-10-18-limit-acceptance.json'
            original.write_text('published snapshot')
            with patch.object(limit_demo,'__file__',str(root/'limit_demo.py')), patch('builtins.print'):
                limit_demo.main()
            self.assertEqual(original.read_text(),'published snapshot')
            self.assertTrue((root/'reports/local/2026-10-18-limit-acceptance.json').exists())
            self.assertTrue((root/'reports/local/2026-10-18-limit-acceptance.md').exists())

    def test_destination_rejects_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                destination(folder,'../snapshot.json')
