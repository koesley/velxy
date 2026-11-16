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
                     'draft_pull_request':'https://github.com/owner/repo/pull/10'}
        return archive,publication

    def mock(self,*,modified=False,non_draft=False,changed_ref=False,extra_file=False):
        calls=[]
        def request(token,method,path,payload=None):
            calls.append(method)
            if '/git/commits/' in path:
                return {'sha':SHA,'parents':[{'sha':'a'*40}]}
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
