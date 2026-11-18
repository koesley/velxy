import sqlite3
import unittest
import lead_attention_board as board
import sales_pipeline

DAY = 86400
NOW = 2000000000

class LeadAttentionBoardTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        sales_pipeline.setup(self.c)
    def tearDown(self):
        self.c.close()
    def add(self, owner, name, stage="new", age=3, email=""):
        ident=sales_pipeline.save(self.c,owner,{"business":name,"stage":stage,"email":email,"value":"125"})
        self.c.execute("UPDATE sales_pipeline_leads SET updated_at=? WHERE id=?",(NOW-age*DAY,ident))
        return ident
    def test_due_and_stage_thresholds(self):
        self.add(1,"New lead",age=2)
        self.add(1,"Recent reply",stage="replied",age=2)
        info=board.attention(self.c,1,NOW)
        self.assertEqual((info["active"],info["needs_review"]),(2,1))
        self.assertEqual(info["displayed"][0]["business"],"New lead")
    def test_tenant_isolation_and_suppression(self):
        self.add(1,"Owner A",email="stop@example.com")
        self.add(2,"Owner B",email="stop@example.com")
        sales_pipeline.set_suppression(self.c,1,"stop@example.com","do_not_contact")
        a=board.attention(self.c,1,NOW)
        b=board.attention(self.c,2,NOW)
        self.assertTrue(a["displayed"][0]["blocked"])
        self.assertFalse(b["displayed"][0]["blocked"])
        self.assertNotIn("Owner B",board.dashboard(self.c,1,NOW))
    def test_closed_leads_excluded(self):
        self.add(1,"Closed",stage="won",age=20)
        self.assertEqual(board.attention(self.c,1,NOW)["active"],0)
    def test_complete_totals_when_display_capped(self):
        for n in range(205):
            self.add(1,"Lead %03d"%n)
        info=board.attention(self.c,1,NOW)
        self.assertEqual((info["active"],info["needs_review"],len(info["displayed"])),(205,205,100))
        self.assertTrue(info["truncated"])
    def test_escape_and_no_automatic_send(self):
        self.add(1,"<script>alert(1)</script>")
        page=board.dashboard(self.c,1,NOW)
        self.assertNotIn("<script>",page)
        self.assertIn("&lt;script&gt;",page)
        self.assertIn("No email is sent",page)
    def test_limit_validation(self):
        with self.assertRaises(ValueError):
            board.attention(self.c,1,NOW,10000)

if __name__=="__main__":
    unittest.main()
