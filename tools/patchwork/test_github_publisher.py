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

    def test_legacy_publisher_uses_atomic_draft_pr(self):
        from unittest.mock import patch
        with patch('atomic_publisher.publish_atomic',
                   return_value={'draft_pull_request':'https://github.com/owner/repo/pull/7',
                                 'atomic_commit':True,'merged':False}) as atomic:
            result = publish('owner/repo', 'main', 'release.zip',
                             approve=True, token='dummy', source_root='repo',
                             evidence_path='evidence.json')
            self.assertTrue(result['atomic_commit'])
            self.assertFalse(result['merged'])
            atomic.assert_called_once()

    def test_missing_policy_root_prevents_all_network_writes(self):
        with tempfile.TemporaryDirectory() as root:
            archive = self.make_zip(root)
            evidence = self.make_evidence(root, archive)
            calls = []
            def mock(token, method, path, payload=None):
                calls.append(method)
                raise AssertionError('Network should not be used')
            with self.assertRaises(ValueError):
                publish('owner/repo', 'main', archive, approve=True, token='dummy',
                        request=mock, evidence_path=evidence)
            self.assertEqual(calls, [])

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
