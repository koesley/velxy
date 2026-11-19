import sqlite3
import unittest
from revenue_execution_workload import summary,page

class WorkloadTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE bos59_leads(id TEXT,workspace_id TEXT,name TEXT)")
        self.c.execute("""CREATE TABLE vx_revenue_tasks29
            (id TEXT,workspace_id TEXT,lead_id TEXT,title TEXT,owner_id INTEGER,
             due_date TEXT,status TEXT,created INTEGER,updated INTEGER)""")
        self.c.executemany("INSERT INTO bos59_leads VALUES (?,?,?)",
                           [("l1","a","<script>"),("l2","b","Other")])
        for i in range(60):
            self.c.execute("INSERT INTO vx_revenue_tasks29 VALUES (?,?,?,?,?,?,?,?,?)",
                           (str(i),"a","l1","Task",1,"2026-11-18",
                            "todo" if i<50 else "done",i,i))
        self.c.execute("INSERT INTO vx_revenue_tasks29 VALUES (?,?,?,?,?,?,?,?,?)",
                       ("secret","b","l2","Private",2,"2026-11-18","todo",0,0))
    def tearDown(self):self.c.close()
    def test_counts_and_tenant_boundary(self):
        counts,due=summary(self.c,"a","2026-11-19")
        self.assertEqual(counts["todo"],50)
        self.assertEqual(counts["done"],10)
        self.assertEqual(due,(50,0,0))
        self.assertEqual(summary(self.c,"b","2026-11-19")[0]["todo"],1)
    def test_pages_are_complete_and_stable(self):
        total,first=page(self.c,"a")
        _,second=page(self.c,"a",number=2)
        _,third=page(self.c,"a",number=3)
        self.assertEqual((total,len(first),len(second),len(third)),(60,25,25,10))
        self.assertEqual(len({r[0] for r in first+second+third}),60)
        self.assertNotIn("secret",[r[0] for r in first+second+third])
    def test_filter_and_invalid_inputs(self):
        self.assertEqual(page(self.c,"a","done")[0],10)
        for status,number in [("other",1),("all",0),("all","bad"),("all",10001)]:
            with self.assertRaises(ValueError):page(self.c,"a",status,number)
    def test_cross_workspace_join_is_scoped(self):
        self.c.execute("INSERT INTO bos59_leads VALUES (?,?,?)",("l1","b","Wrong workspace"))
        self.assertTrue(all(r[1]=="<script>" for r in page(self.c,"a")[1]))

if __name__=="__main__":unittest.main()
