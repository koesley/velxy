"""Offline adversarial tests for GitHub Actions provenance gate."""
import unittest
from ci_provenance import verify_ci_provenance

SHA='a'*40
class ProvenanceTests(unittest.TestCase):
    def fake(self, *, wrong_path=False, wrong_sha=False, duplicate=False, bad_job=False):
        calls=[]
        def request(token,method,path,payload=None):
            calls.append((method,path))
            if '/pulls/18' in path:
                return {'state':'open','draft':True,'head':{'sha':SHA,'repo':{'full_name':'owner/repo'}}}
            if '/check-runs?' in path:
                return {'total_count':1,'check_runs':[{
                    'id':55,'name':'patchwork-repair-ci','status':'completed',
                    'conclusion':'success','head_sha':SHA,'app':{'slug':'github-actions'}}]}
            if '/actions/runs?' in path:
                run={'id':10,'head_sha':'b'*40 if wrong_sha else SHA,
                     'path':'.github/workflows/other.yml' if wrong_path else
                            '.github/workflows/patchwork-repair-pr.yml',
                     'event':'pull_request','status':'completed','conclusion':'success'}
                return {'total_count':2 if duplicate else 1,
                        'workflow_runs':[run,dict(run,id=11)] if duplicate else [run]}
            if '/actions/runs/' in path and '/jobs?' in path:
                return {'total_count':1,'jobs':[{
                    'id':22,'name':'patchwork-repair-ci','status':'completed',
                    'conclusion':'failure' if bad_job else 'success',
                    'head_sha':SHA,
                    'check_run_url':'https://api.github.com/repos/owner/repo/check-runs/55'}]}
            raise AssertionError(path)
        return request,calls

    def test_verified_provenance(self):
        request,calls=self.fake()
        report=verify_ci_provenance('owner/repo',18,token='fake',expected_sha=SHA,request=request)
        self.assertEqual(report['status'],'verified')
        self.assertTrue(all(method=='GET' for method,_ in calls))

    def test_wrong_workflow_rejected(self):
        request,_=self.fake(wrong_path=True)
        with self.assertRaisesRegex(ValueError,'provenance'):
            verify_ci_provenance('owner/repo',18,token='fake',expected_sha=SHA,request=request)

    def test_wrong_commit_rejected(self):
        request,_=self.fake(wrong_sha=True)
        with self.assertRaisesRegex(ValueError,'provenance'):
            verify_ci_provenance('owner/repo',18,token='fake',expected_sha=SHA,request=request)

    def test_duplicate_workflow_rejected(self):
        request,_=self.fake(duplicate=True)
        with self.assertRaisesRegex(ValueError,'unique'):
            verify_ci_provenance('owner/repo',18,token='fake',expected_sha=SHA,request=request)

    def test_failed_job_rejected(self):
        request,_=self.fake(bad_job=True)
        with self.assertRaisesRegex(ValueError,'provenance'):
            verify_ci_provenance('owner/repo',18,token='fake',expected_sha=SHA,request=request)

if __name__=='__main__':
    unittest.main()
