"""V12 integration and negative-gate tests."""
import unittest
from rehearsal import rehearse

class RehearsalTests(unittest.TestCase):
    def test_complete_release_lifecycle(self):
        report=rehearse()
        self.assertEqual(report['status'],'passed')
        self.assertEqual(report['files'],2)
        self.assertTrue(report['source_unchanged'])
        self.assertTrue(report['github_requests_simulated'])
        self.assertTrue(report['docker_execution_simulated'])
        self.assertFalse(report['merged'])
        self.assertFalse(report['deployed'])

if __name__=='__main__':
    unittest.main()
