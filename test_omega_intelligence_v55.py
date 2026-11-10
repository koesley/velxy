import unittest
from unittest.mock import patch
from test_aegis_v54 import AegisTests
import omega_intelligence_v55 as omega

class OmegaTests(AegisTests):
 def test_workspace_isolation_omega(self):
  with self.assertRaises(ValueError):omega.report(self.c,2,self.w)
 def test_read_only_omega(self):
  before=self.c.total_changes
  r=omega.report(self.c,1,self.w)
  self.assertEqual(before,self.c.total_changes)
  self.assertIn('knowledge_graph',r)
 def test_questions_omega(self):
  for question in omega.QUESTIONS:
   self.assertEqual(omega.report(self.c,1,self.w,question)['question'],question)
 def test_invalid_question_omega(self):
  with self.assertRaises(ValueError):omega.report(self.c,1,self.w,'delete')
 def test_scenario_no_fake_dates_omega(self):
  s=omega.scenarios({'open_milestones':4},20)
  self.assertEqual(len(s['scenarios']),3)
  self.assertTrue(all(x['estimated_completion_weeks'] is None for x in s['scenarios']))
 def test_scenario_capacity_omega(self):
  for value in ('nan','inf','0','-1','1001','garbage'):
   with self.assertRaises(ValueError):omega.scenarios({},value)
 def test_graph_edges_omega(self):
  g=omega.graph([{'experiment_id':1,'title':'A','goal':'B','plan_count':1,'baseline':3}])
  self.assertEqual(len(g['edges']),3)
 def test_render_escaping_omega(self):
  r=omega.report(self.c,1,self.w);r['workspace_name']='<script>alert(1)</script>'
  with patch.object(omega,'report',return_value=r):html=omega.render(self.c,1,'csrf',self.w)
  self.assertNotIn('<script>',html)
  self.assertIn('&lt;script&gt;',html)
 def test_no_workspace_omega(self):
  with patch.object(omega.aegis,'report',return_value={'workspace_id':None}):
   self.assertIsNone(omega.report(self.c,1,self.w)['workspace_id'])
 def test_human_approval_omega(self):
  r=omega.report(self.c,1,self.w)
  self.assertTrue(all(s['requires_human_approval'] for s in r['strategies']))

if __name__=='__main__':unittest.main()
