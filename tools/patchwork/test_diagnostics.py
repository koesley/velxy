"""PATCHWORK diagnostics tests. Run: python -m unittest discover -s tools/patchwork -p 'test_*.py'"""
import tempfile
import unittest
from pathlib import Path
from diagnostics import diagnose

class DiagnosticsTests(unittest.TestCase):
    def test_reports_syntax_error_without_modifying_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'broken.py'
            original = 'def bad(:\n  pass\n'
            target.write_text(original)
            report = diagnose(directory)
            self.assertEqual(report['python_files_scanned'], 1)
            self.assertEqual(report['findings'][0]['kind'], 'syntax')
            self.assertEqual(target.read_text(), original)
            self.assertFalse(report['ai_enabled'])

    def test_ignores_dependency_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            ignored = Path(directory) / 'node_modules'
            ignored.mkdir()
            (ignored / 'bad.py').write_text('def bad(:')
            (Path(directory) / 'good.py').write_text('x = 1')
            report = diagnose(directory)
            self.assertEqual(report['python_files_scanned'], 1)
            self.assertEqual(report['findings'], [])

if __name__ == '__main__':
    unittest.main()
