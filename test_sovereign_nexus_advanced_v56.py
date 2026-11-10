import sqlite3,unittest,datetime
from unittest.mock import patch
import sovereign_nexus_v56 as nx
import sovereign_workflows_v56 as wf
import sovereign_workflow_runtime_v56 as rt
class AdvancedNexusTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.a=patch('sovereign_v56.audit').start();self.b=patch('sovereign_v56.access',return_value='owner').start()
  self.w=wf.create(self.c,1,'one','Plan','discover')
 def tearDown(self):patch.stopall();self.c.close()
 def test_components_scoped(self):
  nx.save_component(self.c,1,'one','Recipe',['genesis','approval'])
  self.assertEqual(len(nx.advanced_overview(self.c,1,'one')['components']),1)
  self.assertEqual(nx.advanced_overview(self.c,1,'two')['components'],[])
 def test_invalid_component(self):
  for steps in ([],['execute_shell'],['genesis']*13):
   with self.assertRaises(ValueError):nx.save_component(self.c,1,'one','Test',steps)
 def test_schedule_approval_and_cancel(self):
  future=(datetime.datetime.now()+datetime.timedelta(days=2)).strftime('%Y-%m-%dT%H:%M')
  with self.assertRaises(ValueError):nx.plan_schedule(self.c,1,'one',self.w,future)
  wf.update(self.c,1,'one',self.w,'approve')
  sid=nx.plan_schedule(self.c,1,'one',self.w,future)
  self.assertEqual(len(nx.advanced_overview(self.c,1,'one')['schedules']),1)
  with self.assertRaises(ValueError):nx.cancel_schedule(self.c,1,'two',sid)
  nx.cancel_schedule(self.c,1,'one',sid)
  self.assertEqual(nx.advanced_overview(self.c,1,'one')['schedules'][0]['status'],'cancelled')
 def test_branch_does_not_execute(self):
  wf.update(self.c,1,'one',self.w,'approve');rid=rt.start(self.c,1,'one',self.w)
  decision=nx.review_branch(self.c,1,'one',rid,0,'success')
  self.assertEqual(decision,'eligible')
  self.assertEqual(self.c.execute('SELECT count(*) FROM sv56_workflow_tasks WHERE status="done"').fetchone()[0],0)
  with self.assertRaises(ValueError):nx.review_branch(self.c,1,'two',rid,0,'success')
 def test_html_escaped(self):
  nx.save_component(self.c,1,'one','<script>',['genesis'])
  html=nx.render_advanced(self.c,1,'one','csrf')
  self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
if __name__=='__main__':unittest.main()
