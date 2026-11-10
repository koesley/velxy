import unittest
from unittest.mock import patch
from test_sentinel_v53 import SentinelTests
import aegis_v54 as aegis

class AegisTests(SentinelTests):
 def test_read_only(self):
  before=self.c.total_changes
  r=aegis.report(self.c,1,self.w)
  self.assertEqual(before,self.c.total_changes)
  self.assertIn('dossiers',r)
 def test_workspace_isolation(self):
  with self.assertRaises(ValueError):aegis.report(self.c,2,self.w)
 def test_issue_assessment(self):
  j={'experiment_id':4,'stage':'delivery','baseline':None,'plan_count':0,'overdue_milestones':2,'blocked_milestones':1}
  d=aegis.assess(j)
  self.assertEqual(d['issue_count'],4)
  self.assertEqual(d['issues'][0]['code'],'overdue')
 def test_complete_missing_followup(self):
  d=aegis.assess({'experiment_id':4,'stage':'complete','baseline':2,'followup':None,'direction_matched':None})
  self.assertIn('followup_missing',[x['code'] for x in d['issues']])
 def test_clean_sample_not_certified(self):
  d=aegis.assess({'experiment_id':4,'stage':'complete','baseline':1,'followup':2,'direction_matched':True})
  self.assertEqual(d['readiness'],'ready_for_review')
 def test_csv_injection(self):
  r={'dossiers':[{'experiment_id':1,'title':'=HYPERLINK("x")','goal':'@evil','stage':'delivery','readiness':'review_required','issue_count':0,'issues':[],'evidence':{'baseline':None,'followup':None,'overdue_milestones':0,'blocked_milestones':0,'actual_hours':0}}]}
  content=aegis.csv_export(r)
  self.assertIn("'=HYPERLINK",content)
  self.assertIn("'@evil",content)
 def test_render_escapes(self):
  r=aegis.report(self.c,1,self.w);r['workspace_name']='<script>bad()</script>'
  with patch.object(aegis,'report',return_value=r):page=aegis.render(self.c,1,'csrf',self.w)
  self.assertNotIn('<script>',page)
  self.assertIn('&lt;script&gt;',page)
 def test_missing_workspace(self):
  with patch.object(aegis.sentinel,'report',return_value={'workspace_id':None}):r=aegis.report(self.c,1,self.w)
  self.assertEqual(r['dossiers'],[])

if __name__=='__main__':unittest.main()
