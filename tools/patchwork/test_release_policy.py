"""Regression tests for PATCHWORK release impact policy."""
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from release_policy import analyze

def digest(data):
    return hashlib.sha256(data).hexdigest()

class PolicyTests(unittest.TestCase):
    def fixture(self, root, rel, original, replacement):
        repo=Path(root)/'repo'
        repo.mkdir()
        target=repo/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(original)
        archive=Path(root)/'release.zip'
        manifest={'schema':'patchwork-staged-release-v1','approved_for_staging':True,
                  'files':[{'file':rel,'original_sha256':digest(original.encode()),
                            'replacement_sha256':digest(replacement.encode())}]}
        with zipfile.ZipFile(archive,'w') as out:
            out.writestr('patchwork-manifest.json',json.dumps(manifest))
            out.writestr('proposed/'+rel,replacement)
        return repo,archive

    def test_safe_change_eligible(self):
        with tempfile.TemporaryDirectory() as root:
            repo,archive=self.fixture(root,'app.py','x=1\n','x=2\n')
            report=analyze(repo,archive)
            self.assertEqual(report['status'],'eligible')
            self.assertEqual((repo/'app.py').read_text(),'x=1\n')

    def test_new_exec_is_blocked(self):
        with tempfile.TemporaryDirectory() as root:
            repo,archive=self.fixture(root,'app.py','x=1\n','exec("x=2")\n')
            report=analyze(repo,archive)
            self.assertEqual(report['status'],'blocked')

    def test_sensitive_module_requires_review(self):
        with tempfile.TemporaryDirectory() as root:
            repo,archive=self.fixture(root,'auth/session.py','x=1\n','x=2\n')
            report=analyze(repo,archive)
            self.assertEqual(report['status'],'needs_review')

    def test_change_budget_blocks(self):
        with tempfile.TemporaryDirectory() as root:
            repo,archive=self.fixture(root,'app.py','x=1\n','x=2\ny=3\n')
            report=analyze(repo,archive,max_changed_lines=1)
            self.assertEqual(report['status'],'blocked')

    def test_stale_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            repo,archive=self.fixture(root,'app.py','x=1\n','x=2\n')
            (repo/'app.py').write_text('changed\n')
            with self.assertRaises(ValueError):
                analyze(repo,archive)

if __name__=='__main__':
    unittest.main()
