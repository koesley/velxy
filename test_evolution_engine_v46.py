import unittest,json
from test_synapse_v44 import SynapseTests
import evolution_engine_v46 as engine

class EvolutionTests(SynapseTests):
 def seed(self):
  self.approve()
  self.c.execute("UPDATE core_experiments_v43 SET status='completed',followup=2,followup_sample=10 WHERE id=?",(self.eid,))
  for i in range(2):
   self.c.execute("INSERT INTO core_experiments_v43(id,workspace_id,goal_id,title,hypothesis,planned_action,success_direction,status,baseline,baseline_sample,followup,followup_sample,created_by,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('ev'+str(i),self.w,'goal','Prior result','Tested intervention','Human action','increase','completed',0,10,2,10,1,i))
 def test_empty(self):
  self.assertEqual(len(engine.generate(self.c,1,self.w)),1)
  self.assertEqual(engine.report(self.c,1,self.w)['summary']['draft'],1)
 def test_generate_and_deduplicate(self):
  self.seed();self.assertEqual(len(engine.generate(self.c,1,self.w)),1)
  self.assertEqual(engine.generate(self.c,1,self.w),[])
  self.assertEqual(engine.report(self.c,1,self.w)['summary']['draft'],1)
 def test_workspace_isolation(self):
  self.seed()
  with self.assertRaises(ValueError):engine.generate(self.c,2,self.w)
  with self.assertRaises(ValueError):engine.report(self.c,2,self.w)
 def test_submit_requires_separate_approval(self):
  self.seed();pid=engine.generate(self.c,1,self.w)[0]
  eid=engine.decide(self.c,1,self.w,pid,'submit')
  self.assertEqual(self.c.execute('SELECT status FROM core_experiments_v43 WHERE id=?',(eid,)).fetchone()[0],'proposed')
  with self.assertRaises(ValueError):engine.decide(self.c,1,self.w,pid,'submit')
 def test_dismiss_and_readonly(self):
  self.seed();pid=engine.generate(self.c,1,self.w)[0];engine.decide(self.c,1,self.w,pid,'dismiss')
  before=self.c.total_changes;r=engine.report(self.c,1,self.w)
  self.assertEqual(before,self.c.total_changes);json.dumps(r,allow_nan=False)
  self.assertEqual(r['summary']['dismissed'],1)
 def test_render_escapes_and_business_records_unchanged(self):
  self.seed();before=self.c.execute('SELECT count(*) FROM prime_records').fetchone()[0]
  pid=engine.generate(self.c,1,self.w)[0]
  self.c.execute('UPDATE evolution_proposals_v46 SET title=? WHERE id=?',('<script>alert(1)</script>',pid))
  page=engine.render(self.c,1,'token',self.w)
  self.assertIn('&lt;script&gt;',page);self.assertNotIn('<script>alert(1)</script>',page)
  self.assertEqual(before,self.c.execute('SELECT count(*) FROM prime_records').fetchone()[0])

if __name__=='__main__':unittest.main()
