import unittest
from test_synapse_v44 import SynapseTests
import neural_network_v45 as neural

class NeuralTests(SynapseTests):
 def test_empty_and_readonly(self):
  before=self.c.total_changes
  r=neural.report(self.c,1,self.w)
  self.assertEqual(r['summary']['completed'],0)
  self.assertEqual(self.c.total_changes,before)
 def test_workspace_isolation(self):
  with self.assertRaises(ValueError):neural.report(self.c,2,self.w)
 def test_outcomes_and_direction(self):
  self.approve()
  self.c.execute("UPDATE core_experiments_v43 SET status='completed',followup=2,followup_sample=10 WHERE id=?",(self.eid,))
  r=neural.report(self.c,1,self.w)
  self.assertEqual(r['summary']['improved'],1)
  self.assertEqual(r['experiments'][0]['outcome'],'improved')
  self.assertEqual(r['summary']['limited_evidence'],1)
 def test_pattern_thresholds(self):
  self.approve()
  self.c.execute("UPDATE core_experiments_v43 SET status='completed',followup=2,followup_sample=10 WHERE id=?",(self.eid,))
  self.assertFalse(neural.report(self.c,1,self.w)['opportunities'])
  for i in range(2):
   self.c.execute("INSERT INTO core_experiments_v43(id,workspace_id,goal_id,title,hypothesis,planned_action,success_direction,status,baseline,baseline_sample,followup,followup_sample,created_by,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('extra'+str(i),self.w,'goal','Second test','hypothesis','action','increase','completed',0,10,2,10,1,i))
  r=neural.report(self.c,1,self.w)
  self.assertEqual(r['goal_patterns'][0]['completed'],3)
  self.assertEqual(r['opportunities'][0]['priority'],'investigate')
 def test_escaped_render_and_json(self):
  self.c.execute("UPDATE core_experiments_v43 SET title='<img src=x onerror=alert(1)>' WHERE id=?",(self.eid,))
  page=neural.render(self.c,1,self.w)
  self.assertIn('&lt;img',page)
  self.assertNotIn('<img src=x',page)
  import json
  json.dumps(neural.report(self.c,1,self.w),allow_nan=False)
 def test_nonfinite_excluded(self):
  r=('id','title','goal','completed','increase',float('nan'),2,10,10,0,1,'Goal')
  self.assertEqual(neural._classify(r)['outcome'],'invalid-data')
if __name__=='__main__':unittest.main()
