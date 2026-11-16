"""Tests for review-only PATCHWORK repair proposals."""
import tempfile
import unittest
from pathlib import Path
from repair import propose_missing_colon

class RepairTests(unittest.TestCase):
    def test_proposes_colon_without_changing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'example.py'
            source = 'if True\n    print("ok")\n'
            path.write_text(source)
            result = propose_missing_colon(directory, 'example.py')
            self.assertEqual(result['status'], 'proposed')
            self.assertIn('+if True:', result['diff'])
            self.assertEqual(path.read_text(), source)
            self.assertFalse(result['applied'])

    def test_does_not_guess_other_repairs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'broken.py'
            path.write_text('def broken(:\n pass\n')
            result = propose_missing_colon(directory, 'broken.py')
            self.assertEqual(result['status'], 'unsupported')
            self.assertEqual(result['diff'], '')

    def test_rejects_escape_from_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises((ValueError, FileNotFoundError)):
                propose_missing_colon(directory, '../outside.py')

if __name__ == '__main__':
    unittest.main()
