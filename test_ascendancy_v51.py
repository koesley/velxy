import unittest
from test_singularity_v50 import SingularityTests
import ascendancy_v51 as ascendancy

class AscendancyTests(SingularityTests):
 def test_workspace_isolation(self):
  with self.assertRaises(ValueError):ascendancy.report(self.c,2,self.w)
 def test_action_filter_validation(self):
  with self.assertRaises(ValueError):ascendancy.report(self.c,1,self.w,'bogus')
 def test_workflow_stages_and_read_only(self):
  before=self.c.total_changes
  r=ascendancy.report(self.c,1,self.w)
  self.assertEqual(len(r['stages']),6)
  self.assertTrue(r['journeys'])
  self.assertEqual(before,self.c.total_changes)
 def test_filter_and_export(self):
  r=ascendancy.report(self.c,1,self.w,'delivery')
  self.assertTrue(all(a['stage']=='deliver' for a in r['actions']))
  self.assertIn(b'experiment_id',ascendancy.csv_export(self.c,1,self.w))
 def test_escape_user_content(self):
  page=ascendancy.render(self.c,1,'csrf',self.w)
  self.assertIn('ASCENDANCY',page)
  self.assertIn('aria-label=',page)
 def test_csv_formula_sanitized(self):
  import unittest.mock as mock
  payload={'workspace_id':self.w,'workspace_name':'=DANGER','actions':[{'stage':'deliver','priority':'high','title':'=CMD()','reason':'@evil','overdue':0,'experiment_id':None}]}
  with mock.patch.object(ascendancy,'report',return_value=payload):
   csv=ascendancy.csv_export(self.c,1,self.w).decode('utf-8-sig')
  self.assertIn("'=DANGER",csv)
  self.assertIn("'=CMD()",csv)
  self.assertIn("'@evil",csv)

if __name__=='__main__':unittest.main()
