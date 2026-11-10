import sqlite3,tempfile,unittest,json
from pathlib import Path
import atlas_v38
from titanium_v36 import save_report
class AtlasTests(unittest.TestCase):
 def setup_db(self):
  c=sqlite3.connect(':memory:')
  c.executescript('CREATE TABLE empire_workspaces(id TEXT,name TEXT,created INTEGER);CREATE TABLE empire_members(workspace_id TEXT,user_id INTEGER,role TEXT);INSERT INTO empire_workspaces VALUES("w","<script>alert(1)</script>",1);INSERT INTO empire_members VALUES("w",1,"owner");')
  return c
 def test_workspace_isolation(self):
  with tempfile.TemporaryDirectory() as d,self.setup_db() as c:
   with self.assertRaises(ValueError):atlas_v38.render(c,1,'other',d)
 def test_html_escape(self):
  with tempfile.TemporaryDirectory() as d,self.setup_db() as c:
   page=atlas_v38.render(c,1,'w',d)
   self.assertIn('&lt;script&gt;',page)
   self.assertNotIn('<script>alert(1)</script>',page)
 def test_readiness_requires_verified_real_reports(self):
  with tempfile.TemporaryDirectory() as d:
   save_report(d,'browser_journey',{'passed':True,'checks':{'ok':True}})
   self.assertTrue(atlas_v38.report_summary(d)['browser_journey']['passed'])
   self.assertFalse(atlas_v38.readiness(d)['production_ready'])
 def test_skipped_browser_not_success(self):
  with tempfile.TemporaryDirectory() as d:
   save_report(d,'browser_journey',{'passed':False,'skipped':True})
   self.assertFalse(atlas_v38.report_summary(d)['browser_journey']['passed'])
 def test_no_workspace_onboarding(self):
  with tempfile.TemporaryDirectory() as d,self.setup_db() as c:
   self.assertIn('Create workspace',atlas_v38.render(c,2,'',d))
if __name__=='__main__':unittest.main()
