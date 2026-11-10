import unittest
from unittest.mock import patch
from test_titan_intelligence_v52 import TitanTests
import sentinel_v53 as sentinel

class SentinelTests(TitanTests):
 def test_read_only(self):
  before=self.c.total_changes
  r=sentinel.report(self.c,1,self.w)
  self.assertEqual(before,self.c.total_changes)
  self.assertEqual(len(r['checks']),5)
 def test_workspace_isolation(self):
  with self.assertRaises(ValueError):sentinel.report(self.c,2,self.w)
 def test_escapes_workspace_name(self):
  r=sentinel.report(self.c,1,self.w)
  r['workspace_name']='<img src=x onerror=alert(1)>'
  with patch.object(sentinel,'report',return_value=r):page=sentinel.render(self.c,1,'csrf',self.w)
  self.assertNotIn('<img',page)
  self.assertIn('&lt;img',page)
 def test_rules_with_mocked_evidence(self):
  t={'workspace_id':'w','workspace_name':'Demo','role':'owner'}
  s={'journeys':[{'experiment_id':7,'stage':'delivery','baseline':None,'plan_count':0,'blocked_milestones':2,'overdue_milestones':1},{'experiment_id':8,'stage':'measurement','baseline':3,'followup':None}], 'limitations':[]}
  with patch.object(sentinel.titan,'report',return_value=t),patch.object(sentinel.singularity,'report',return_value=s):r=sentinel.report(self.c,1,self.w)
  self.assertEqual(r['summary']['flagged'],5)
  self.assertEqual(r['summary']['sampled_experiments'],2)
 def test_empty_sample_does_not_claim_clean(self):
  t={'workspace_id':'w','workspace_name':'Demo','role':'owner'}
  with patch.object(sentinel.titan,'report',return_value=t),patch.object(sentinel.singularity,'report',return_value={'journeys':[],'limitations':[]}):r=sentinel.report(self.c,1,self.w)
  self.assertTrue(all(x['status']=='clear_in_sample' for x in r['checks']))
  self.assertTrue(any('sampled' in x.lower() for x in r['limitations']))

if __name__=='__main__':unittest.main()
