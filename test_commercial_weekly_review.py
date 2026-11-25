import unittest
from demo_guidance import weekly_review

class WeeklyReviewTests(unittest.TestCase):
    def test_empty_and_invalid(self):
        for a,b in [(0,0),(-1,2),(True,2),(1,None)]:
            self.assertEqual(weekly_review(a,b), ())
    def test_rejected_only(self):
        self.assertEqual(len(weekly_review(0,4)),1)
    def test_accepted_only(self):
        self.assertEqual(len(weekly_review(4,0)),3)
    def test_mixed(self):
        self.assertEqual(len(weekly_review(4,2)),4)
