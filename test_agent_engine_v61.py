import sqlite3
import unittest
from unittest.mock import patch
import agent_engine_v61 as engine
import business_agents_v59 as agents

class AgentEngineTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.access=patch.object(agents.core,"access",return_value="owner")
        self.audit=patch.object(agents.core,"audit")
        self.access.start();self.audit.start()
    def tearDown(self):
        self.access.stop();self.audit.stop();self.c.close()
    def test_offline_plan_and_owner_review(self):
        with patch.dict("os.environ",{"VELXTRIA_V61_AI_ENABLED":"0"}):
            rid=engine.plan(self.c,1,"a","Grow the business")
        runs=engine.list_runs(self.c,1,"a")
        self.assertEqual(runs[0]["status"],"awaiting_review")
        self.assertEqual(runs[0]["provider"],"offline_rules")
        self.assertEqual(engine.list_runs(self.c,1,"b"),[])
        jid=engine.approve_as_task(self.c,1,"a",rid,"sales")
        self.assertEqual(agents.overview(self.c,1,"a")["jobs"][0]["status"],"in_review")
        self.assertTrue(jid)
    def test_invalid_objective(self):
        with self.assertRaises(ValueError):engine.plan(self.c,1,"a","no")
    def test_model_failure_is_not_exposed(self):
        def broken(_):raise RuntimeError("SECRET_TOKEN")
        rid=engine.plan(self.c,1,"a","Improve customer service",model_call=broken)
        run=engine.list_runs(self.c,1,"a")[0]
        self.assertEqual(run["status"],"failed")
        self.assertNotIn("SECRET_TOKEN",str(run))

if __name__=="__main__":unittest.main()
