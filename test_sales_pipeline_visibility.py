import sqlite3
import time
import unittest
from unittest.mock import patch
import sales_pipeline


class CompletePipelineVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        sales_pipeline.setup(self.db)

    def tearDown(self):
        self.db.close()

    def add(self, owner, business, stage="new", value=10, age_days=0):
        lead = sales_pipeline.save(self.db, owner, {
            "business": business, "stage": stage, "value": str(value)})
        self.db.execute("UPDATE sales_pipeline_leads SET updated_at=? WHERE id=?",
                        (int(time.time()) - age_days * 86400, lead))
        return lead

    def test_totals_cover_more_than_preview_limit(self):
        for n in range(205):
            self.add(1, "Business %03d" % n, "proposal", 10)
        page = sales_pipeline.dashboard(self.db, 1, "token")
        self.assertIn("205 total leads", page)
        self.assertIn("Estimated open opportunities: $2050", page)

    def test_other_owner_not_counted_or_displayed(self):
        self.add(1, "Owner One", "won", 500)
        self.add(2, "Private Business", "proposal", 999, 30)
        page = sales_pipeline.dashboard(self.db, 1, "token")
        self.assertIn("1 total leads", page)
        self.assertIn("Self-reported won deals: $500", page)
        self.assertNotIn("Private Business", page)
        self.assertNotIn("$999", page)

    def test_stale_review_ignores_won_and_lost(self):
        self.add(1, "Needs Review", "contacted", 12, 30)
        self.add(1, "Already Won", "won", 20, 30)
        self.add(1, "Closed Lost", "lost", 20, 30)
        page = sales_pipeline.dashboard(self.db, 1, "token")
        self.assertIn("1 open leads have not been updated", page)
        self.assertIn("Needs Review", page)
        self.assertNotIn("Already Won ·", page)
        self.assertNotIn("Closed Lost ·", page)

    def test_stale_review_escapes_business(self):
        self.add(1, "<img src=x onerror=alert(1)>", "new", 1, 20)
        page = sales_pipeline.dashboard(self.db, 1, "token")
        self.assertNotIn("<img", page)
        self.assertIn("&lt;img", page)

    def test_review_bounded_to_ten_and_count_is_complete(self):
        for n in range(13):
            self.add(1, "Old Business %02d" % n, age_days=20+n)
        page = sales_pipeline.dashboard(self.db, 1, "token")
        self.assertIn("13 open leads have not been updated", page)
        self.assertIn("Showing the 10 oldest of 13 records", page)
        self.assertNotIn("Old Business 00 ·", page)

    def test_recent_open_lead_not_flagged(self):
        self.add(1, "Fresh Business", "meeting", 100, 1)
        page = sales_pipeline.dashboard(self.db, 1, "token")
        self.assertIn("0 open leads have not been updated", page)


if __name__ == "__main__":
    unittest.main()
