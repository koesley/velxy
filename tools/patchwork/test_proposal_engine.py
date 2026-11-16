"""PATCHWORK proposal validation tests."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from proposal_engine import validate_proposal

class ProposalTests(unittest.TestCase):
    def test_valid_proposal_is_read_only(self):
        with tempfile.TemporaryDirectory() as root:
            file = Path(root) / 'app.py'
            file.write_text('answer = 1\n')
            result = validate_proposal(root, 'app.py', 'answer = 2\n')
            self.assertEqual(result['status'], 'ready_for_review')
            self.assertIn('+answer = 2', result['diff'])
            self.assertEqual(file.read_text(), 'answer = 1\n')
            self.assertFalse(result['tests_run'])
            self.assertFalse(result['applied'])

    def test_rejects_invalid_syntax(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / 'app.py').write_text('x = 1\n')
            result = validate_proposal(root, 'app.py', 'def bad(:\n')
            self.assertEqual(result['status'], 'rejected')

    def test_rejects_stale_proposals(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / 'app.py').write_text('x = 1\n')
            with self.assertRaises(ValueError):
                validate_proposal(root, 'app.py', 'x = 2\n', expected_sha256='0' * 64)

    def test_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                validate_proposal(root, '../app.py', 'x = 1\n')

    def test_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as root:
            outside = Path(root).parent / ('patchwork-external-' + Path(root).name + '.py')
            outside.write_text('x = 1\n')
            try:
                (Path(root) / 'link.py').symlink_to(outside)
                with self.assertRaises(ValueError):
                    validate_proposal(root, 'link.py', 'x = 2\n')
            finally:
                outside.unlink(missing_ok=True)

if __name__ == '__main__':
    unittest.main()
