import json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import apex_v37,empire_v19

class ApexTests(unittest.TestCase):
 def test_authenticated_customer_journey(self):
  with tempfile.TemporaryDirectory() as d:
   r=apex_v37.run_journey(d)
   self.assertTrue(r['result']['passed'],r['result'])
   self.assertGreaterEqual(r['result']['count'],25)
   self.assertTrue(apex_v37.read_reports(d)[0]['verified'])
 def test_tamper_detection(self):
  with tempfile.TemporaryDirectory() as d:
   r=apex_v37.save_report(d,'authenticated_journey',{'passed':True})
   p=apex_v37.reports_dir(d)/(r['id']+'.json') if hasattr(apex_v37,'reports_dir') else Path(d)/'titanium_evidence'/(r['id']+'.json')
   obj=json.loads(p.read_text());obj['result']['passed']=False;p.write_text(json.dumps(obj))
   self.assertFalse(apex_v37.read_reports(d)[0]['verified'])
 def test_render_escapes_and_no_execution(self):
  with tempfile.TemporaryDirectory() as d,sqlite3.connect(':memory:') as c:
   c.executescript('CREATE TABLE empire_workspaces(id TEXT,name TEXT,created INTEGER);CREATE TABLE empire_members(workspace_id TEXT,user_id INTEGER,role TEXT);INSERT INTO empire_workspaces VALUES("w","<script>",1);INSERT INTO empire_members VALUES("w",1,"owner");')
   page=apex_v37.render(c,1,'w',d)
   self.assertIn('&lt;script&gt;',page)
   self.assertNotIn('<script>',page)
   self.assertNotIn('action="/apex" method="post"',page)
 def test_other_workspace_denied(self):
  with sqlite3.connect(':memory:') as c:
   c.executescript('CREATE TABLE empire_workspaces(id TEXT,name TEXT,created INTEGER);CREATE TABLE empire_members(workspace_id TEXT,user_id INTEGER,role TEXT);INSERT INTO empire_workspaces VALUES("w","test",1);INSERT INTO empire_members VALUES("w",1,"owner");')
   with self.assertRaises(ValueError):apex_v37.render(c,1,'other','/tmp')
if __name__=='__main__':unittest.main()
