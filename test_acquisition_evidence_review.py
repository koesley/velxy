"""Regression coverage for acquisition evidence review and safe presentation."""
import unittest
from acquisition_intelligence_v35 import review_channels, render_channel_review

def record(source,leads,won,cost,tasks=0,completed=0):
    return {"source":source,"leads":leads,"won_leads":won,
            "cost_cents":cost,"tasks":tasks,"completed_tasks":completed}

class AcquisitionEvidenceReviewTests(unittest.TestCase):
    def test_prioritizes_spend_without_leads(self):
        findings=review_channels([record("organic",4,0,0),record("ads",0,0,12000)])
        self.assertEqual(findings[0]["source"],"ads")
        self.assertIn("no leads attributed",findings[0]["flags"][0])
    def test_no_spend_is_unknown_not_free(self):
        finding=review_channels([record("referral",8,3,0)])[0]
        self.assertIn("cost is unknown",finding["flags"][0])
    def test_small_sample_and_task_followup(self):
        finding=review_channels([record("local",3,0,4000,5,2)])[0]
        self.assertTrue(any("Small lead sample" in x for x in finding["flags"]))
        self.assertTrue(any("incomplete" in x for x in finding["flags"]))
    def test_does_not_claim_conversion_failure_on_small_sample(self):
        finding=review_channels([record("local",2,0,100)])[0]
        self.assertFalse(any("No won-marked" in x for x in finding["flags"]))
    def test_rejects_inconsistent_counts(self):
        for row in [record("a",2,3,100),record("b",1,0,-1),record("c",1,0,0,2,3)]:
            with self.subTest(row=row),self.assertRaises(ValueError):
                review_channels([row])
    def test_rejects_invalid_threshold(self):
        for threshold in (0,101,True,1.5):
            with self.subTest(threshold=threshold),self.assertRaises(ValueError):
                review_channels([],threshold)
    def test_escapes_names_and_workspace_url(self):
        page=render_channel_review([record('<img src=x onerror=alert(1)>',2,0,0)],'other&workspace')
        self.assertNotIn('<img',page)
        self.assertIn('&lt;img',page)
        self.assertIn('other%26workspace',page)
    def test_empty_state_and_disclosures(self):
        page=render_channel_review([],'w')
        self.assertIn('No source records',page)
        self.assertIn('not forecasts',page)
if __name__=="__main__":
    unittest.main()
