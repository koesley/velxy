"""Negative safety tests for live GitHub integration gate."""
import unittest
from live_integration import run

class LiveIntegrationSafetyTests(unittest.TestCase):
    def test_requires_approval_before_network(self):
        calls=[]
        def request(*args):
            calls.append(args)
            raise AssertionError('Network must not be accessed')
        with self.assertRaises(ValueError):
            run('owner/disposable','main',token='dummy',request=request,
                expected_repository='owner/disposable')
        self.assertFalse(calls)

    def test_production_repository_is_forbidden(self):
        calls=[]
        def request(*args):
            calls.append(args)
            raise AssertionError('Network must not be accessed')
        with self.assertRaises(ValueError):
            run('koesley/velxy','main',token='dummy',approve=True,request=request,
                expected_repository='koesley/velxy')
        self.assertFalse(calls)

    def test_repository_allowlist_is_mandatory(self):
        calls=[]
        def request(*args):
            calls.append(args)
            raise AssertionError('Network must not be accessed')
        with self.assertRaises(ValueError):
            run('owner/disposable','main',token='dummy',approve=True,request=request,
                expected_repository='owner/other')
        self.assertFalse(calls)

    def test_disposable_fixture_mismatch_prevents_writes(self):
        calls=[]
        def request(token,method,path,payload=None):
            calls.append((method,path))
            if path=='/repos/owner/disposable':
                return {'full_name':'owner/disposable','default_branch':'main',
                        'archived':False,'disabled':False}
            return {'content':'d3Jvbmc='}
        with self.assertRaises(ValueError):
            run('owner/disposable','main',token='dummy',approve=True,request=request,
                expected_repository='owner/disposable')
        self.assertFalse(any(method!='GET' for method,_ in calls))

if __name__=='__main__':
    unittest.main()
