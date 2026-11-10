import json, os, sqlite3, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import sentinel_v34

class SentinelTests(unittest.TestCase):
 def test_health_read_only(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'test.sqlite3'
   with sqlite3.connect(p) as c:c.execute('CREATE TABLE example(id INTEGER PRIMARY KEY)')
   before=p.read_bytes()
   h=sentinel_v34.database_health(p)
   self.assertEqual(h['integrity'],'ok');self.assertEqual(h['foreign_key_violations'],0)
   self.assertEqual(before,p.read_bytes())
 def test_checksum_detects_tampering(self):
  with tempfile.TemporaryDirectory() as d:
   folder=sentinel_v34.evidence_dir(d);folder.mkdir()
   r={'schema':1,'run_id':'test','started':0,'status':'passed','tests':[]}
   r['sha256']=sentinel_v34._digest(r)
   p=folder/'test.json';p.write_text(json.dumps(r))
   self.assertTrue(sentinel_v34.load_reports(d)[0]['verified'])
   r['status']='failed';p.write_text(json.dumps(r))
   self.assertFalse(sentinel_v34.load_reports(d)[0]['verified'])
 def test_fixed_runner_and_isolation(self):
  with tempfile.TemporaryDirectory() as d:
   class Result: returncode=0;stdout='OK';stderr=''
   with patch.object(sentinel_v34.subprocess,'run',return_value=Result()) as run:
    report=sentinel_v34.run_suite(d,30)
    args=run.call_args
    self.assertEqual(args.args[0][:4],[sentinel_v34.sys.executable,'-m','unittest','-v'])
    self.assertNotEqual(args.kwargs['env']['VELXTRIA_DATA_DIR'],d)
    self.assertEqual(args.kwargs['timeout'],30)
    self.assertEqual(report['status'],'passed')
    self.assertTrue(sentinel_v34.load_reports(d)[0]['verified'])
 def test_timeout_validation(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):sentinel_v34.run_suite(d,99999)
if __name__=='__main__':unittest.main()
