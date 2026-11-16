"""Offline tests for GitHub draft PR publishing."""
import base64
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from github_publisher import load_release, publish

def digest(data):
    return hashlib.sha256(data).hexdigest()

class PublisherTests(unittest.TestCase):
    def make_zip(self, root, rel='src/a.py'):
        path = Path(root)/'release.zip'
        old, new = b'x = 1\n', b'x = 2\n'
        manifest = {'schema': 'patchwork-staged-release-v1', 'approved_for_staging': True,
                    'files': [{'file': rel, 'original_sha256': digest(old),
                               'replacement_sha256': digest(new)}]}
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('patchwork-manifest.json', json.dumps(manifest))
            archive.writestr('proposed/'+rel, new)
        return path

    def make_evidence(self, root, archive):
        path = Path(root)/'verification.json'
        path.write_text(json.dumps({
            'schema': 'patchwork-isolated-verification-v1',
            'status': 'passed', 'exit_code': 0, 'tests_discovered': 2,
            'release_sha256': digest(archive.read_bytes()),
            'source_repository_modified': False, 'tests_executed_on_host': False
        }))
        return path

    def test_requires_explicit_approval(self):
        with tempfile.TemporaryDirectory() as root:
            archive = self.make_zip(root)
            with self.assertRaises(ValueError):
                publish('owner/repo', 'main', archive, token='dummy')

    def test_draft_pr_only(self):
        with tempfile.TemporaryDirectory() as root:
            archive = self.make_zip(root)
            evidence = self.make_evidence(root, archive)
            calls = []
            def mock(token, method, path, payload=None):
                calls.append((method, path, payload))
                if path.endswith('/git/ref/heads/main'):
                    return {'object': {'sha': 'a'*40}}
                if '/contents/src/a.py' in path and method == 'GET':
                    return {'sha': 'blobsha', 'content': base64.b64encode(b'x = 1\n').decode()}
                if path.endswith('/pulls'):
                    return {'html_url': 'https://github.com/owner/repo/pull/7'}
                return {}
            result = publish('owner/repo', 'main', archive, approve=True, token='dummy', request=mock, evidence_path=evidence)
            self.assertEqual(result['draft_pull_request'], 'https://github.com/owner/repo/pull/7')
            self.assertTrue(next(payload for method, path, payload in calls if path.endswith('/pulls'))['draft'])
            self.assertFalse(result['merged'])
            self.assertFalse(any('/merges' in path for _, path, _ in calls))

    def test_stale_base_prevents_writes(self):
        with tempfile.TemporaryDirectory() as root:
            archive = self.make_zip(root)
            calls = []
            def mock(token, method, path, payload=None):
                calls.append(method)
                if '/git/ref/' in path:
                    return {'object': {'sha': 'a'*40}}
                return {'sha': 'blobsha', 'content': base64.b64encode(b'changed').decode()}
            with self.assertRaises(ValueError):
                publish('owner/repo', 'main', archive, approve=True, token='dummy', request=mock, evidence_path=evidence)
            self.assertEqual(calls, ['GET','GET'])

    def test_missing_or_stale_test_evidence_blocks_publication(self):
        with tempfile.TemporaryDirectory() as root:
            archive = self.make_zip(root)
            with self.assertRaises(ValueError):
                publish('owner/repo', 'main', archive, approve=True, token='dummy')
            evidence = self.make_evidence(root, archive)
            data = json.loads(evidence.read_text())
            data['release_sha256'] = '0'*64
            evidence.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                publish('owner/repo', 'main', archive, approve=True, token='dummy',
                        evidence_path=evidence)

    def test_zip_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            archive = self.make_zip(root, '../bad.py')
            with self.assertRaises(ValueError):
                load_release(archive)

if __name__ == '__main__':
    unittest.main()
