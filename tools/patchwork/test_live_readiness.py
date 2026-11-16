"""Regression tests for read-only GitHub integration readiness."""
import base64
import unittest
from live_readiness import audit

SHA='a'*40

class ReadinessTests(unittest.TestCase):
    def mock(self, *, private=True, fixture=True, push=True):
        calls=[]
        def request(token,method,path,payload=None):
            calls.append((method,path))
            if path=='/repos/owner/disposable':
                return {'full_name':'owner/disposable','private':private,
                        'default_branch':'main','archived':False,'disabled':False,
                        'permissions':{'push':push,'pull':True}}
            if '/git/ref/heads/' in path:
                return {'object':{'sha':SHA}}
            if '/contents/' in path:
                data=b'def patchwork_fixture():\n    return 1\n' if fixture else b'wrong'
                return {'content':base64.b64encode(data).decode()}
            raise AssertionError('Unexpected API call')
        return request,calls

    def test_ready_never_writes(self):
        request,calls=self.mock()
        result=audit('owner/disposable','main',token='fake',
                     expected_repository='owner/disposable',request=request)
        self.assertEqual(result['status'],'ready')
        self.assertTrue(all(method=='GET' for method,_ in calls))
        self.assertFalse(result['writes_performed'])

    def test_public_repository_blocks_before_fixture(self):
        request,calls=self.mock(private=False)
        result=audit('owner/disposable','main',token='fake',
                     expected_repository='owner/disposable',request=request)
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(len(calls),1)

    def test_bad_fixture_blocks(self):
        request,calls=self.mock(fixture=False)
        result=audit('owner/disposable','main',token='fake',
                     expected_repository='owner/disposable',request=request)
        self.assertEqual(result['status'],'blocked')
        self.assertTrue(all(method=='GET' for method,_ in calls))

    def test_no_push_permission_blocks(self):
        request,calls=self.mock(push=False)
        result=audit('owner/disposable','main',token='fake',
                     expected_repository='owner/disposable',request=request)
        self.assertEqual(result['status'],'blocked')

    def test_production_denied_before_network(self):
        request,calls=self.mock()
        with self.assertRaises(ValueError):
            audit('koesley/velxy','main',token='fake',
                  expected_repository='koesley/velxy',request=request)
        self.assertFalse(calls)

if __name__=='__main__':
    unittest.main()
