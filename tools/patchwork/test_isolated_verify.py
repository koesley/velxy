"""Offline tests for isolated repair verification (Docker is mocked)."""
import hashlib
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from isolated_verify import verify

class VerifyTests(unittest.TestCase):
    def fixture(self, temp):
        base = Path(temp)
        repo = base/'repo'
        repo.mkdir()
        (repo/'app.py').write_text('x=1\n')
        (repo/'test_app.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n')
        archive = base/'release.zip'
        before, after = b'x=1\n', b'x=2\n'
        manifest = {'schema': 'patchwork-staged-release-v1', 'approved_for_staging': True,
                    'files': [{'file': 'app.py',
                               'original_sha256': hashlib.sha256(before).hexdigest(),
                               'replacement_sha256': hashlib.sha256(after).hexdigest()}]}
        with zipfile.ZipFile(archive, 'w') as out:
            out.writestr('patchwork-manifest.json', json.dumps(manifest))
            out.writestr('proposed/app.py', after)
        return repo, archive

    def test_requires_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, archive = self.fixture(temp)
            with self.assertRaises(ValueError):
                verify(repo, archive)

    def test_container_constraints_and_original_untouched(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, archive = self.fixture(temp)
            def fake(command, **kwargs):
                self.assertIn('--network', command)
                self.assertEqual(command[command.index('--network')+1], 'none')
                self.assertIn('--read-only', command)
                self.assertIn('no-new-privileges', command)
                self.assertIn('--cap-drop', command)
                self.assertIn('readonly', next(x for x in command if x.startswith('type=bind')))
                return subprocess.CompletedProcess(command, 0, '', 'Ran 2 tests in 0.01s\\nOK')
            result = verify(repo, archive, approve=True, runner=fake)
            self.assertEqual(result['status'], 'passed')
            self.assertEqual((repo/'app.py').read_text(), 'x=1\n')
            self.assertFalse(result['deployed'])

    def test_stale_release_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, archive = self.fixture(temp)
            (repo/'app.py').write_text('changed\n')
            with self.assertRaises(ValueError):
                verify(repo, archive, approve=True, runner=lambda *a, **kw: self.fail('runner called'))

    def test_failed_tests_not_reported_as_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, archive = self.fixture(temp)
            result = verify(repo, archive, approve=True,
                            runner=lambda command, **kw: subprocess.CompletedProcess(command, 1, '', 'failed'))
            self.assertEqual(result['status'], 'failed')

if __name__ == '__main__':
    unittest.main()
