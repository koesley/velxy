"""Offline tests for publication postflight verification."""
import base64
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from publication_postflight import verify_publication

SHA='f'*40
BRANCH='patchwork/review-'+SHA[:16]
OLD=b'x=1\n'
NEW=b'x=2\n'

class PostflightTests(unittest.TestCase):
    def fixture(self,root):
        archive=Path(root)/'release.zip'
        digest=lambda data:hashlib.sha256(data).hexdigest()
        manifest={'schema':'patchwork-staged-release-v1','approved_for_staging':True,
                  'files':[{'file':'app.py','original_sha256':digest(OLD),
                            'replacement_sha256':digest(NEW)}]}
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('patchwork-manifest.json',json.dumps(manifest))
            z.writestr('proposed/app.py',NEW)
        publication={'atomic_commit':True,'commit_sha':SHA,'branch':BRANCH,'files':1,
                     'draft_pull_request':'https://github.com/owner/repo/pull/10',
                     'base_commit_sha':'a'*40,'release_sha256':digest(archive.read_bytes())}
        self.release_digest=digest(archive.read_bytes())
        return archive,publication

    def mock(self,*,modified=False,non_draft=False,changed_ref=False,extra_file=False,
             wrong_parent=False):
        calls=[]
        def request(token,method,path,payload=None):
            calls.append(method)
            if '/git/commits/' in path:
                return {'sha':SHA,'parents':[{'sha':'b'*40 if wrong_parent else 'a'*40}],
                        'message':'Patchwork-Release-SHA256: '+self.release_digest+'\\nPatchwork-Base-SHA: '+'a'*40}
            if '/commits/' in path:
                changed=[{'filename':'app.py','status':'modified'}]
                if extra_file:
                    changed.append({'filename':'secrets.py','status':'modified'})
                return {'sha':SHA,'parents':[{'sha':'a'*40}],'files':changed}
            if '/git/ref/heads/' in path:
                return {'object':{'sha':'a'*40 if changed_ref else SHA}}
            if '/contents/app.py' in path:
                return {'content':base64.b64encode(OLD if modified else NEW).decode()}
            if '/pulls?' in path:
                return [{'draft':not non_draft,'head':{'sha':SHA,'ref':BRANCH},
                         'base':{'ref':'main'},'html_url':'https://github.com/owner/repo/pull/10'}]
            raise AssertionError('Unexpected GitHub request: '+path)
        return request,calls

    def test_verifies_all_objects_without_writes(self):
        with tempfile.TemporaryDirectory() as root:
            archive,pub=self.fixture(root)
            request,calls=self.mock()
            report=verify_publication('owner/repo','main',archive,pub,token='fake',request=request)
            self.assertEqual(report['status'],'verified')
            self.assertEqual(report['files_verified'],1)
            self.assertTrue(all(method=='GET' for method in calls))

    def test_modified_remote_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            archive,pub=self.fixture(root)
            request,_=self.mock(modified=True)
            with self.assertRaisesRegex(ValueError,'differs'):
                verify_publication('owner/repo','main',archive,pub,token='fake',request=request)

    def test_non_draft_pr_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            archive,pub=self.fixture(root)
            request,_=self.mock(non_draft=True)
            with self.assertRaisesRegex(ValueError,'identity'):
                verify_publication('owner/repo','main',archive,pub,token='fake',request=request)

    def test_wrong_commit_parent_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            archive,pub=self.fixture(root)
            request,_=self.mock(wrong_parent=True)
            with self.assertRaisesRegex(ValueError,'parent'):
                verify_publication('owner/repo','main',archive,pub,token='fake',request=request)

    def test_release_digest_mismatch_is_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as root:
            archive,pub=self.fixture(root)
            pub['release_sha256']='0'*64
            request,calls=self.mock()
            with self.assertRaisesRegex(ValueError,'digest'):
                verify_publication('owner/repo','main',archive,pub,token='fake',request=request)
            self.assertFalse(calls)

    def test_unapproved_extra_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            archive,pub=self.fixture(root)
            request,_=self.mock(extra_file=True)
            with self.assertRaisesRegex(ValueError,'file count'):
                verify_publication('owner/repo','main',archive,pub,token='fake',request=request)

    def test_moved_branch_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            archive,pub=self.fixture(root)
            request,_=self.mock(changed_ref=True)
            with self.assertRaisesRegex(ValueError,'changed'):
                verify_publication('owner/repo','main',archive,pub,token='fake',request=request)

if __name__=='__main__':
    unittest.main()
