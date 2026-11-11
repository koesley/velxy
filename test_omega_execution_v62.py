"""V62 execution permission, idempotence and workspace isolation tests."""
import sqlite3
import unittest
import omega_mission_v61 as mission
import omega_execution_v62 as execution
class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        for sql in (
          "CREATE TABLE empire_members(workspace_id TEXT,user_id TEXT)",
          "CREATE TABLE v61_missions(id TEXT PRIMARY KEY,workspace TEXT,owner TEXT,objective TEXT,status TEXT,created INTEGER)",
          "CREATE TABLE v61_tasks(id TEXT PRIMARY KEY,workspace TEXT,mission TEXT,role TEXT,title TEXT,description TEXT,status TEXT,created INTEGER)",
          "CREATE TABLE v61_events(id TEXT PRIMARY KEY,workspace TEXT,mission TEXT,actor TEXT,event TEXT,details TEXT,created INTEGER)",
          "CREATE TABLE v62_runs(id TEXT PRIMARY KEY,workspace TEXT,mission TEXT,task TEXT,tool TEXT,status TEXT,output TEXT,actor TEXT,created INTEGER)",
        ):self.c.execute(sql)
        self.c.execute("INSERT INTO empire_members VALUES ('a','alice')")
        self.c.execute("INSERT INTO empire_members VALUES ('b','bob')")
        mission.act(self.c,"alice","a",{"action":"create","objective":"Launch a professional website agency"})
        self.mid=self.c.execute("SELECT id FROM v61_missions").fetchone()[0]
        self.tid=self.c.execute("SELECT id FROM v61_tasks WHERE role='Marketing'").fetchone()[0]
    def tearDown(self):self.c.close()
    def test_approval_and_active_required(self):
        with self.assertRaises(ValueError):execution.run(self.c,"alice","a",self.tid)
        mission.act(self.c,"alice","a",{"action":"approve","task":self.tid})
        with self.assertRaises(ValueError):execution.run(self.c,"alice","a",self.tid)
        mission.act(self.c,"alice","a",{"action":"activate","mission":self.mid})
        execution.run(self.c,"alice","a",self.tid)
        self.assertIn("DRAFT ONLY",self.c.execute("SELECT output FROM v62_runs").fetchone()[0])
        with self.assertRaises(ValueError):execution.run(self.c,"alice","a",self.tid)
    def test_tenant_isolation(self):
        with self.assertRaises(ValueError):execution.run(self.c,"bob","a",self.tid)
        with self.assertRaises(ValueError):execution.render(self.c,"bob","a","csrf")
    def test_all_six_tools(self):
        for role,(_,label) in execution.TOOLS.items():
            self.assertTrue(execution.produce(role,"Launch agency",label,"test"))
if __name__=="__main__":unittest.main()
