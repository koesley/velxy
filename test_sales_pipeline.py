import sqlite3
import unittest
import sales_pipeline

class SalesPipelineTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        sales_pipeline.setup(self.c)
    def tearDown(self):
        self.c.close()
    def test_owner_isolation(self):
        lid=sales_pipeline.save(self.c,1,{"business":"Example Cafe","stage":"new","value":"49"})
        html=sales_pipeline.dashboard(self.c,2,"csrf")
        self.assertNotIn("Example Cafe",html)
        with self.assertRaises(ValueError):
            sales_pipeline.save(self.c,2,{"lead_id":lid,"business":"Changed","stage":"won"})
    def test_stage_update(self):
        lid=sales_pipeline.save(self.c,1,{"business":"Example Cafe","stage":"new"})
        sales_pipeline.save(self.c,1,{"lead_id":lid,"business":"Example Cafe","stage":"won","value":"49"})
        self.assertIn("Self-reported won deals: $49",sales_pipeline.dashboard(self.c,1,"csrf"))
    def test_bad_stage(self):
        with self.assertRaises(ValueError):
            sales_pipeline.save(self.c,1,{"business":"Example Cafe","stage":"invented"})
    def test_escaping(self):
        sales_pipeline.save(self.c,1,{"business":"<script>alert(1)</script>","stage":"new"})
        html=sales_pipeline.dashboard(self.c,1,"csrf")
        self.assertNotIn("<script>",html)
        self.assertIn("&lt;script&gt;",html)

if __name__=="__main__":
    unittest.main()
