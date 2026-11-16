"""V17: legacy publication compatibility cannot bypass policy or atomicity."""
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from github_publisher import publish

def sha(data):
    return hashlib.sha256(data).hexdigest()

class PublisherUnificationTests(unittest.TestCase):
    def fixture(self, root, *, risky=False):
        source=root/'repo'
        source.mkdir()
        old=b'def answer():\n    return 1\n'
        new=(b'def answer():\n    exec("x=1")\n    return 2\n' if risky
             else b'def answer():\n    return 2\n')
        (source/'app.py').write_bytes(old)
        archive=root/'release.zip'
        manifest={'schema':'patchwork-staged-release-v1','approved_for_staging':True,
                  'files':[{'file':'app.py','original_sha256':sha(old),
                            'replacement_sha256':sha(new)}]}
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('patchwork-manifest.json',json.dumps(manifest))
            z.writestr('proposed/app.py',new)
        evidence=root/'evidence.json'
        evidence.write_text(json.dumps({
            'schema':'patchwork-isolated-verification-v1',
            'status':'passed','exit_code':0,'tests_discovered':1,
            'release_sha256':sha(archive.read_bytes()),
            'source_repository_modified':False,'tests_executed_on_host':False
        }))
        return source,archive,evidence

    def test_legacy_api_requires_local_policy_root_before_network(self):
        with tempfile.TemporaryDirectory() as temp:
            source,archive,evidence=self.fixture(Path(temp))
            calls=[]
            def request(*args):
                calls.append(args)
                raise AssertionError('No GitHub calls allowed')
            with self.assertRaises(ValueError):
                publish('owner/repo','main',archive,approve=True,token='fake',
                        evidence_path=evidence,request=request)
            self.assertFalse(calls)

    def test_legacy_api_blocks_risky_repair_before_network(self):
        with tempfile.TemporaryDirectory() as temp:
            source,archive,evidence=self.fixture(Path(temp),risky=True)
            calls=[]
            def request(*args):
                calls.append(args)
                raise AssertionError('No GitHub calls allowed')
            with self.assertRaisesRegex(ValueError,'policy blocked'):
                publish('owner/repo','main',archive,approve=True,token='fake',
                        evidence_path=evidence,source_root=source,request=request)
            self.assertFalse(calls)

    def test_legacy_api_delegates_to_atomic_publisher(self):
        import unittest.mock
        with unittest.mock.patch('atomic_publisher.publish_atomic',
                                 return_value={'atomic_commit':True}) as atomic:
            result=publish('owner/repo','main','release.zip',approve=True,
                           token='fake',source_root='repo',evidence_path='evidence.json')
            self.assertTrue(result['atomic_commit'])
            self.assertEqual(atomic.call_count,1)

if __name__=='__main__':
    unittest.main()
