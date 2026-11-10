import json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import titanium_v36

class TitaniumTests(unittest.TestCase):
 def test_restore_is_disposable_and_preserves_source(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'portal.sqlite3'
   with sqlite3.connect(p) as c:
    c.execute('CREATE TABLE sample(id INTEGER PRIMARY KEY, value TEXT)')
    c.execute('INSERT INTO sample VALUES(1,?)',('hello',))
   before=p.read_bytes()
   r=titanium_v36.recovery_rehearsal(p,d)
   self.assertTrue(r['result']['passed'])
   self.assertEqual(r['result']['records_compared'],1)
   self.assertEqual(before,p.read_bytes())
   self.assertTrue(titanium_v36.read_reports(d)[0]['verified'])
 def test_detect_foreign_key_violations(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'portal.sqlite3'
   with sqlite3.connect(p) as c:
    c.executescript('CREATE TABLE parent(id INTEGER PRIMARY KEY);CREATE TABLE child(pid INTEGER REFERENCES parent(id));INSERT INTO child VALUES(999);')
   self.assertFalse(titanium_v36.recovery_rehearsal(p,d)['result']['passed'])
 def test_tampered_report_is_invalid(self):
  with tempfile.TemporaryDirectory() as d:
   r=titanium_v36.save_report(d,'http_smoke',{'passed':True})
   p=titanium_v36.reports_dir(d)/(r['id']+'.json')
   data=json.loads(p.read_text());data['result']['passed']=False;p.write_text(json.dumps(data))
   self.assertFalse(titanium_v36.read_reports(d)[0]['verified'])
 def test_http_smoke_real_server(self):
  with tempfile.TemporaryDirectory() as d:
   r=titanium_v36.http_smoke(d,30)
   self.assertTrue(r['result']['passed'],r['result'])
   self.assertTrue(titanium_v36.read_reports(d)[0]['verified'])
 def test_render_is_read_only_and_escapes(self):
  import empire_v19
  with tempfile.TemporaryDirectory() as d,sqlite3.connect(':memory:') as c:
   c.executescript('CREATE TABLE empire_workspaces(id TEXT,name TEXT,created INTEGER);CREATE TABLE empire_members(workspace_id TEXT,user_id INTEGER,role TEXT);INSERT INTO empire_workspaces VALUES("w","<bad>",1);INSERT INTO empire_members VALUES("w",1,"owner");')
   with patch.object(empire_v19,'role',return_value='owner'):
    html=titanium_v36.render(c,1,'w',d)
   self.assertIn('&lt;bad&gt;',html)
   self.assertNotIn('<bad>',html)
if __name__=='__main__':unittest.main()
