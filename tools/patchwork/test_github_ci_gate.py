"""Offline regression tests for immutable GitHub CI gate."""
import unittest
from github_ci_gate import inspect_pr

SHA = 'a'*40

class GateTests(unittest.TestCase):
    def fake(self, conclusion='success', head_sha=SHA, draft=True, runs=1):
        def request(token, method, path, payload=None):
            if '/pulls/' in path:
                return {'state':'open', 'draft':draft,
                        'head':{'sha':SHA,'repo':{'full_name':'owner/repo'}}}
            return {'total_count':runs, 'check_runs':[{
                'name':'patchwork-repair-ci', 'status':'completed', 'conclusion':conclusion,
                'head_sha':head_sha, 'app':{'slug':'github-actions'}
            } for _ in range(runs)]}
        return request

    def test_passes_matching_immutable_commit(self):
        report=inspect_pr('owner/repo', 7, token='dummy', expected_sha=SHA,
                          request=self.fake())
        self.assertEqual(report['status'], 'passed')
        self.assertFalse(report['merged'])

    def test_rejects_failed_checks(self):
        report=inspect_pr('owner/repo', 7, token='dummy', expected_sha=SHA,
                          request=self.fake(conclusion='failure'))
        self.assertEqual(report['status'], 'blocked')

    def test_rejects_stale_head(self):
        with self.assertRaises(ValueError):
            inspect_pr('owner/repo', 7, token='dummy', expected_sha='b'*40,
                       request=self.fake())

    def test_rejects_duplicate_checks(self):
        report=inspect_pr('owner/repo', 7, token='dummy', expected_sha=SHA,
                          request=self.fake(runs=2))
        self.assertEqual(report['status'], 'blocked')

    def test_rejects_wrong_commit_check(self):
        report=inspect_pr('owner/repo', 7, token='dummy', expected_sha=SHA,
                          request=self.fake(head_sha='b'*40))
        self.assertEqual(report['status'], 'blocked')

    def test_rejects_non_draft(self):
        with self.assertRaises(ValueError):
            inspect_pr('owner/repo', 7, token='dummy', expected_sha=SHA,
                       request=self.fake(draft=False))

if __name__ == '__main__':
    unittest.main()
