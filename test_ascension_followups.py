import sqlite3
import unittest
import sales_pipeline
import sovereign_ascension as asc
import ascension_followups as studio

class FollowupStudioTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        sales_pipeline.setup(self.c)
        asc.setup(self.c)
        self.lead=sales_pipeline.save(self.c,1,{"business":"Example Cafe","email":"hello@example.com","stage":"proposal"})
        self.action=asc.action(self.c,1,self.lead,"stalled_deal","approved")
    def tearDown(self):
        self.c.close()
    def clear(self):
        sales_pipeline.set_suppression(self.c,1,"hello@example.com","verified_clear","Current public business contact page")
    def test_unknown_contact_cannot_prepare(self):
        with self.assertRaises(ValueError):studio.prepare(self.c,1,self.action)
    def test_verified_contact_creates_unsent_draft(self):
        self.clear()
        ident=studio.prepare(self.c,1,self.action)
        row=self.c.execute("SELECT status,recipient FROM ascension_followup_drafts WHERE id=?",(ident,)).fetchone()
        self.assertEqual(row,("draft","hello@example.com"))
    def test_cross_owner_denied(self):
        self.clear()
        with self.assertRaises(ValueError):studio.prepare(self.c,2,self.action)
    def test_opt_out_blocks_revision(self):
        self.clear()
        ident=studio.prepare(self.c,1,self.action)
        sales_pipeline.set_suppression(self.c,1,"hello@example.com","do_not_contact")
        with self.assertRaises(ValueError):studio.revise(self.c,1,ident,"Subject","Body")
    def test_duplicate_draft_rejected(self):
        self.clear()
        studio.prepare(self.c,1,self.action)
        with self.assertRaises(ValueError):studio.prepare(self.c,1,self.action)
    def test_escape_in_rendered_draft(self):
        self.clear()
        ident=studio.prepare(self.c,1,self.action)
        studio.revise(self.c,1,ident,"<script>alert(1)</script>","Hello")
        page=studio.dashboard(self.c,1,"csrf")
        self.assertNotIn("<script>",page)
        self.assertIn("&lt;script&gt;",page)
    def test_empty_first_visit(self):
        empty=sqlite3.connect(":memory:")
        try:self.assertIn("Follow-up Studio",studio.dashboard(empty,1,"csrf"))
        finally:empty.close()

if __name__=="__main__":
    unittest.main()
