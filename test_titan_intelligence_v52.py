import unittest
from unittest.mock import patch
from test_ascendancy_v51 import AscendancyTests
import titan_intelligence_v52 as titan

class TitanTests(AscendancyTests):
 def test_titan_workspace_isolation(self):
  with self.assertRaises(ValueError):titan.report(self.c,2,self.w)
 def test_titan_read_only(self):
  before=self.c.total_changes
  r=titan.report(self.c,1,self.w)
  self.assertEqual(before,self.c.total_changes)
  self.assertTrue(r['findings'])
 def test_titan_evidence_and_human_review(self):
  r=titan.report(self.c,1,self.w)
  self.assertTrue(all(f['requires_human_review'] and f['evidence']['source'] for f in r['findings']))
 def test_titan_render_escapes_customer_input(self):
  r=titan.report(self.c,1,self.w)
  r['workspace_name']='<script>alert(1)</script>'
  with patch.object(titan,'report',return_value=r): page=titan.render(self.c,1,'csrf',self.w)
  self.assertNotIn('<script>',page)
  self.assertIn('&lt;script&gt;',page)
 def test_titan_no_false_positive(self):
  with patch.object(titan.asc,'report',return_value={'workspace_id':'a','workspace_name':'Demo','role':'owner'}),patch.object(titan.singularity,'report',return_value={'summary':{},'journeys':[],'limitations':[]}):
   r=titan.report(self.c,1,self.w)
  self.assertEqual(r['findings'][0]['code'],'review')
 def test_titan_priority_and_audit_fields(self):
  r=titan.report(self.c,1,self.w)
  self.assertTrue(all(f['code'] and f['stage'] and f['recommended_action'] for f in r['findings']))

if __name__=='__main__':unittest.main()
