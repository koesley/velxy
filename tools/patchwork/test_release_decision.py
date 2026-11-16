"""Integration and adversarial tests for the PATCHWORK review-readiness gate."""
import unittest
from unittest.mock import patch
from release_decision import assess_release

SHA = 'a'*40
PUBLICATION = {
    'atomic_commit': True, 'commit_sha': SHA, 'base_commit_sha': 'b'*40,
    'branch': 'patchwork/review-'+SHA[:16], 'files': 1,
    'release_sha256': 'c'*64,
    'draft_pull_request': 'https://github.com/owner/repo/pull/18',
}
PR = {'state': 'open', 'draft': True,
      'head': {'sha': SHA, 'ref': PUBLICATION['branch'],
               'repo': {'full_name': 'owner/repo'}},
      'base': {'ref': 'main'}, 'html_url': PUBLICATION['draft_pull_request']}

class DecisionTests(unittest.TestCase):
    def run_gate(self, *, publication_ok=True, ci_ok=True, pr=None):
        calls = []
        def request(token, method, path, payload=None):
            calls.append((method, path))
            if path.endswith('/pulls/18'):
                return PR.copy() if pr is None else pr
            raise AssertionError('Unexpected request: ' + path)
        def postflight(*args, **kwargs):
            if not publication_ok:
                raise ValueError('Remote file mismatch')
            return {'status': 'verified', 'head_sha': SHA}
        def provenance(*args, **kwargs):
            if not ci_ok:
                raise ValueError('Required workflow has not passed')
            return {'status': 'verified', 'head_sha': SHA}
        with patch('release_decision.verify_publication', side_effect=postflight), \
             patch('release_decision.verify_ci_provenance', side_effect=provenance):
            result = assess_release('owner/repo', 'main', 'release.zip',
                                    dict(PUBLICATION), 18, token='fake', request=request)
        return result, calls

    def test_success_requires_all_three_gates(self):
        result, calls = self.run_gate()
        self.assertEqual(result['status'], 'review_ready')
        self.assertTrue(all(v == 'passed' for v in result['checks'].values()))
        self.assertFalse(result['merge_authorized'])
        self.assertFalse(result['deployment_authorized'])
        self.assertEqual(calls, [('GET', '/repos/owner/repo/pulls/18')])

    def test_publication_mismatch_blocks_even_with_green_ci(self):
        result, _ = self.run_gate(publication_ok=False)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['checks']['publication_integrity'], 'blocked')
        self.assertEqual(result['checks']['github_actions_provenance'], 'passed')

    def test_missing_ci_blocks_even_with_valid_publication(self):
        result, _ = self.run_gate(ci_ok=False)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['checks']['github_actions_provenance'], 'blocked')

    def test_pr_changed_after_checks_blocks(self):
        moved = dict(PR, head=dict(PR['head'], sha='d'*40))
        result, _ = self.run_gate(pr=moved)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['checks']['final_pr_identity'], 'blocked')

    def test_ready_for_review_not_draft_is_rejected(self):
        result, _ = self.run_gate(pr=dict(PR, draft=False))
        self.assertEqual(result['status'], 'blocked')

    def test_base_branch_change_is_rejected(self):
        result, _ = self.run_gate(pr=dict(PR, base={'ref': 'other'}))
        self.assertEqual(result['status'], 'blocked')

    def test_invalid_identity_prevents_any_network(self):
        called = []
        with self.assertRaises(ValueError):
            assess_release('owner/repo', 'main', 'release.zip',
                           dict(PUBLICATION), True, token='fake',
                           request=lambda *a: called.append(a))
        self.assertFalse(called)

if __name__ == '__main__':
    unittest.main()
