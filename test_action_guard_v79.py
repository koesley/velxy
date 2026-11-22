import unittest
from action_guard_v79 import Proposal, evaluate

class GuardTests(unittest.TestCase):
    def test_paused(self):
        self.assertEqual(evaluate(Proposal('a','summarize'),workspace_id='a')['decision'],'deny')
    def test_safe_action(self):
        self.assertEqual(evaluate(Proposal('a','summarize'),workspace_id='a',paused=False)['decision'],'allow')
    def test_cross_tenant(self):
        self.assertEqual(evaluate(Proposal('a','summarize'),workspace_id='b',paused=False)['reason'],'workspace_mismatch')
    def test_unknown(self):
        self.assertEqual(evaluate(Proposal('a','run_shell'),workspace_id='a',paused=False)['decision'],'deny')
    def test_sensitive_review(self):
        self.assertEqual(evaluate(Proposal('a','send_message'),workspace_id='a',paused=False)['decision'],'review')
    def test_approved(self):
        self.assertEqual(evaluate(Proposal('a','send_message',approval_id='ok'),workspace_id='a',paused=False,approved_ids={'ok'})['decision'],'allow')
    def test_money_review(self):
        self.assertEqual(evaluate(Proposal('a','summarize','5'),workspace_id='a',paused=False)['decision'],'review')
    def test_nan_denied(self):
        self.assertEqual(evaluate(Proposal('a','summarize','NaN'),workspace_id='a',paused=False)['decision'],'deny')
    def test_negative_denied(self):
        self.assertEqual(evaluate(Proposal('a','summarize','-1'),workspace_id='a',paused=False)['decision'],'deny')
    def test_bad_pause(self):
        with self.assertRaises(ValueError): evaluate(Proposal('a','summarize'),workspace_id='a',paused=0)
if __name__=='__main__': unittest.main()
