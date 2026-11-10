import sqlite3,unittest
from unittest.mock import patch
import sovereign_nexus_v56 as nx
import sovereign_workflows_v56 as wf
class NexusTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.a=patch('sovereign_v56.audit').start();self.b=patch('sovereign_v56.access',return_value='owner').start()
 def tearDown(self):patch.stopall();self.c.close()
 def test_rules_and_scope(self):
  w=wf.create(self.c,1,'one','Example plan','discover');nx.set_rule(self.c,1,'one',w,1,'on_blocked');self.assertEqual(nx.overview(self.c,1,'one')['workflows'][0]['canvas'][1]['condition'],'on_blocked');self.assertEqual(nx.overview(self.c,1,'two')['workflows'],[])
  with self.assertRaises(ValueError):nx.set_rule(self.c,1,'two',w,1,'always')
 def test_invalid_rules(self):
  w=wf.create(self.c,1,'one','Example plan','discover')
  for idx,condition in [(0,'on_blocked'),(90,'always'),(1,'execute_python')]:
   with self.assertRaises(ValueError):nx.set_rule(self.c,1,'one',w,idx,condition)
  wf.update(self.c,1,'one',w,'approve')
  with self.assertRaises(ValueError):nx.set_rule(self.c,1,'one',w,1,'always')
 def test_notifications(self):
  w=wf.create(self.c,1,'one','Example plan','discover');wf.update(self.c,1,'one',w,'approve')
  import sovereign_workflow_runtime_v56 as rt
  rid=rt.start(self.c,1,'one',w);nx.notify(self.c,1,'one',rid,'review','Review this workflow')
  data=nx.overview(self.c,1,'one');self.assertEqual(data['stats']['unread'],1);nid=data['notifications'][0]['id']
  with self.assertRaises(ValueError):nx.mark_seen(self.c,1,'two',nid)
  nx.mark_seen(self.c,1,'one',nid);self.assertEqual(nx.overview(self.c,1,'one')['stats']['unread'],0)
 def test_escaping(self):
  wf.create(self.c,1,'one','<script>alert(1)</script>','discover')
  page=nx.render(self.c,1,'one','csrf');self.assertNotIn('<script>',page);self.assertIn('&lt;script&gt;',page)
 def test_no_unapproved_execution(self):
  w=wf.create(self.c,1,'one','Example plan','discover');nx.set_rule(self.c,1,'one',w,1,'on_success')
  self.assertEqual(self.c.execute('SELECT count(*) FROM sv56_workflow_runs').fetchone()[0],0)
if __name__=='__main__':unittest.main()
