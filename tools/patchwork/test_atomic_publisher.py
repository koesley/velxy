"""Offline integration tests for atomic repair publishing."""
import base64
import hashlib
import json
import tempfile
import unittest
import zipfile
import urllib.error
from pathlib import Path
from atomic_publisher import publish_atomic

OLD = b'x=1\n'
NEW = b'x=2\n'
SHA = 'a'*40

def digest(data):
    return hashlib.sha256(data).hexdigest()

class AtomicPublisherTests(unittest.TestCase):
    def fixture(self, root):
        root = Path(root)
        archive = root/'release.zip'
        manifest = {'schema':'patchwork-staged-release-v1','approved_for_staging':True,
                    'files':[{'file':'app.py','original_sha256':digest(OLD),
                              'replacement_sha256':digest(NEW)}]}
        with zipfile.ZipFile(archive,'w') as out:
            out.writestr('patchwork-manifest.json',json.dumps(manifest))
            out.writestr('proposed/app.py',NEW)
        evidence = root/'report.json'
        evidence.write_text(json.dumps({
            'schema':'patchwork-isolated-verification-v1','status':'passed',
            'exit_code':0,'tests_discovered':2,'release_sha256':digest(archive.read_bytes()),
            'source_repository_modified':False,'tests_executed_on_host':False}))
        repo=root/'repo'
        repo.mkdir()
        (repo/'app.py').write_bytes(OLD)
        self.release_digest=digest(archive.read_bytes())
        return archive,evidence,repo

    def fake(self, stale=False, moving=False):
        calls=[]
        def request(token, method, path, payload=None):
            calls.append((method,path,payload))
            if '/git/ref/heads/patchwork/' in path:
                count=sum('/git/ref/heads/patchwork/' in p for _,p,_ in calls)
                if count == 1:
                    raise urllib.error.HTTPError(path,404,'Not Found',{},None)
                return {'object':{'sha':'f'*40}}
            if '/git/ref/heads/' in path:
                count=sum('/git/ref/heads/main' in p for _,p,_ in calls)
                return {'object':{'sha':'b'*40 if moving and count>1 else SHA}}
            if path.endswith('/git/commits/'+SHA):
                return {'tree':{'sha':'c'*40}}
            if '/commits/' in path and method == 'GET' and '/git/commits/' not in path:
                return {'sha':'f'*40,'parents':[{'sha':SHA}],
                        'files':[{'filename':'app.py','status':'modified'}]}
            if '/contents/app.py' in path:
                contents = (NEW if '?ref='+'f'*40 in path else (b'wrong' if stale else OLD))
                return {'content':base64.b64encode(contents).decode()}
            if path.endswith('/git/blobs'):
                return {'sha':'d'*40}
            if path.endswith('/git/trees'):
                return {'sha':'e'*40}
            if path.endswith('/git/commits'):
                return {'sha':'f'*40}
            if path.endswith('/git/commits/'+'f'*40):
                return {'sha':'f'*40,'parents':[{'sha':SHA}],
                        'message':'Patchwork-Release-SHA256: '+self.release_digest+'\\nPatchwork-Base-SHA: '+SHA}
            if '/pulls?' in path:
                count=sum('/pulls?' in p for _,p,_ in calls)
                if count == 1:
                    return []
                return [{'draft':True,'head':{'sha':'f'*40,'ref':'patchwork/review-'+'f'*16},
                         'base':{'ref':'main'},'html_url':'https://github.com/owner/repo/pull/10'}]
            if path.endswith('/pulls'):
                return {'html_url':'https://github.com/owner/repo/pull/10'}
            return {}
        return request,calls

    def test_single_commit_draft_pr(self):
        with tempfile.TemporaryDirectory() as temp:
            archive,evidence,repo=self.fixture(temp)
            request,calls=self.fake()
            result=publish_atomic('owner/repo','main',archive,approve=True,
                                  token='dummy',evidence_path=evidence,source_root=repo,request=request)
            self.assertTrue(result['atomic_commit'])
            self.assertTrue(result['postflight_verified'])
            self.assertEqual(sum(method=='POST' and path.endswith('/git/commits')
                                 for method,path,_ in calls),1)
            self.assertFalse(any(method=='PUT' for method,_,_ in calls))
            self.assertTrue(next(payload for method,path,payload in calls
                                 if path.endswith('/pulls'))['draft'])

    def test_stale_source_prevents_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            archive,evidence,repo=self.fixture(temp)
            request,calls=self.fake(stale=True)
            with self.assertRaises(ValueError):
                publish_atomic('owner/repo','main',archive,approve=True,token='dummy',
                               evidence_path=evidence,source_root=repo,request=request)
            self.assertFalse(any(method!='GET' for method,_,_ in calls))

    def test_moved_base_prevents_branch_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            archive,evidence,repo=self.fixture(temp)
            request,calls=self.fake(moving=True)
            with self.assertRaises(ValueError):
                publish_atomic('owner/repo','main',archive,approve=True,token='dummy',
                               evidence_path=evidence,source_root=repo,request=request)
            self.assertFalse(any(path.endswith('/git/refs') for _,path,_ in calls))

    def test_policy_blocks_risky_repair_before_network(self):
        with tempfile.TemporaryDirectory() as temp:
            archive,evidence,repo=self.fixture(temp)
            # Replace archive contents with a dangerous call, then update
            # the evidence digest to keep the policy as the failing gate.
            changed=b'exec("x=2")\\n'
            manifest={'schema':'patchwork-staged-release-v1','approved_for_staging':True,
                      'files':[{'file':'app.py','original_sha256':digest(OLD),
                                'replacement_sha256':digest(changed)}]}
            with zipfile.ZipFile(archive,'w') as out:
                out.writestr('patchwork-manifest.json',json.dumps(manifest))
                out.writestr('proposed/app.py',changed)
            report=json.loads(evidence.read_text())
            report['release_sha256']=digest(archive.read_bytes())
            evidence.write_text(json.dumps(report))
            request,calls=self.fake()
            with self.assertRaises(ValueError):
                publish_atomic('owner/repo','main',archive,approve=True,token='dummy',
                               evidence_path=evidence,source_root=repo,request=request)
            self.assertFalse(calls)

    def test_missing_evidence_prevents_network(self):
        with tempfile.TemporaryDirectory() as temp:
            archive,evidence,repo=self.fixture(temp)
            request,calls=self.fake()
            with self.assertRaises(ValueError):
                publish_atomic('owner/repo','main',archive,approve=True,token='dummy',
                               request=request)
            self.assertFalse(calls)

if __name__=='__main__':
    unittest.main()
