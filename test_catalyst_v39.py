import json,sqlite3,tempfile,time,unittest
from pathlib import Path
import catalyst_v39
from titanium_v36 import save_report,reports_dir
class CatalystTests(unittest.TestCase):
 def test_missing_evidence_blocks(self):
  with tempfile.TemporaryDirectory() as d:self.assertFalse(catalyst_v39.preflight(d)['passed'])
 def test_valid_evidence_passes_local_checks_not_production(self):
  with tempfile.TemporaryDirectory() as d:
   for kind in ('authenticated_journey','http_smoke','restore_rehearsal','browser_journey'):save_report(d,kind,{'passed':True})
   r=catalyst_v39.preflight(d);self.assertTrue(r['passed']);self.assertFalse(r['production_ready'])
 def test_tampering_blocks(self):
  with tempfile.TemporaryDirectory() as d:
   r=save_report(d,'browser_journey',{'passed':True});p=reports_dir(d)/(r['id']+'.json');data=json.loads(p.read_text());data['result']['passed']=False;p.write_text(json.dumps(data))
   self.assertFalse(catalyst_v39.preflight(d)['checks']['browser_journey']['passed'])
 def test_stale_blocks(self):
  with tempfile.TemporaryDirectory() as d:
   r=save_report(d,'browser_journey',{'passed':True});p=reports_dir(d)/(r['id']+'.json');data=json.loads(p.read_text());data['timestamp']=int(time.time())-100000;from titanium_v36 import digest;data['sha256']=digest({k:v for k,v in data.items() if k!='sha256'});p.write_text(json.dumps(data))
   self.assertFalse(catalyst_v39.preflight(d)['checks']['browser_journey']['passed'])
 def test_workspace_access_and_html_escape(self):
  with tempfile.TemporaryDirectory() as d,sqlite3.connect(':memory:') as c:
   c.executescript('CREATE TABLE empire_workspaces(id TEXT,name TEXT,created INTEGER);CREATE TABLE empire_members(workspace_id TEXT,user_id INTEGER,role TEXT);INSERT INTO empire_workspaces VALUES("w","<script>x</script>",1);INSERT INTO empire_members VALUES("w",1,"owner");')
   self.assertIn('&lt;script&gt;',catalyst_v39.render(c,1,'w',d))
   with self.assertRaises(ValueError):catalyst_v39.render(c,1,'other',d)
if __name__=='__main__':unittest.main()
