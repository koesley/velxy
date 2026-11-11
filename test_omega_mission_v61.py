"""Isolated OMEGA mission state and authorization tests."""
import sqlite3
import unittest
import omega_mission_v61 as omega
class OmegaTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        for sql in (
          "CREATE TABLE empire_members(workspace_id TEXT,user_id TEXT)",
          "CREATE TABLE v61_missions(id TEXT PRIMARY KEY,workspace TEXT,owner TEXT,objective TEXT,status TEXT,created INTEGER)",
          "CREATE TABLE v61_tasks(id TEXT PRIMARY KEY,workspace TEXT,mission TEXT,role TEXT,title TEXT,description TEXT,status TEXT,created INTEGER)",
          "CREATE TABLE v61_events(id TEXT PRIMARY KEY,workspace TEXT,mission TEXT,actor TEXT,event TEXT,details TEXT,created INTEGER)",
        ):self.c.execute(sql)
        self.c.execute("INSERT INTO empire_members VALUES ('a','alice')")
        self.c.execute("INSERT INTO empire_members VALUES ('b','bob')")
    def tearDown(self):self.c.close()
    def test_mission_lifecycle(self):
        omega.act(self.c,"alice","a",{"action":"create","objective":"Build a website design agency"})
        mid=self.c.execute("SELECT id FROM v61_missions").fetchone()[0]
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM v61_tasks").fetchone()[0],6)
        omega.act(self.c,"alice","a",{"action":"activate","mission":mid})
        with self.assertRaises(ValueError):omega.act(self.c,"alice","a",{"action":"finish","mission":mid})
        tasks=self.c.execute("SELECT id FROM v61_tasks").fetchall()
        for (tid,) in tasks:
            omega.act(self.c,"alice","a",{"action":"approve","task":tid})
            omega.act(self.c,"alice","a",{"action":"complete","task":tid})
        omega.act(self.c,"alice","a",{"action":"finish","mission":mid})
        self.assertIn("completed",omega.render(self.c,"alice","a","csrf"))
        self.assertGreater(self.c.execute("SELECT COUNT(*) FROM v61_events").fetchone()[0],6)
    def test_workspace_isolation(self):
        with self.assertRaises(ValueError):omega.act(self.c,"bob","a",{"action":"create","objective":"Build a design agency"})
        with self.assertRaises(ValueError):omega.render(self.c,"bob","a","csrf")
    def test_no_skip_approval(self):
        omega.act(self.c,"alice","a",{"action":"create","objective":"Build a website design agency"})
        tid=self.c.execute("SELECT id FROM v61_tasks LIMIT 1").fetchone()[0]
        with self.assertRaises(ValueError):omega.act(self.c,"alice","a",{"action":"complete","task":tid})
if __name__=="__main__":unittest.main()
