import sqlite3,unittest
from unittest.mock import patch
import sovereign_omniverse_v57 as om
class OmniverseTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.access=patch('sovereign_v56.access',return_value='owner').start();self.audit=patch('sovereign_v56.audit').start()
 def tearDown(self):patch.stopall();self.c.close()
 def test_idempotent_and_execution(self):
  jid=om.enqueue(self.c,1,'a','workspace_health','health-key-123')
  self.assertEqual(jid,om.enqueue(self.c,1,'a','workspace_health','health-key-123'))
  self.assertEqual(om.run_one(self.c,1,'a',jid)['imports'],0)
  with self.assertRaises(ValueError):om.run_one(self.c,1,'a',jid)
  self.assertEqual(om.overview(self.c,1,'a')['counts']['done'],1)
 def test_tenant_isolation(self):
  jid=om.enqueue(self.c,1,'a','workspace_health','health-key-123')
  with self.assertRaises(ValueError):om.run_one(self.c,1,'b',jid)
  self.assertEqual(om.overview(self.c,1,'b')['jobs'],[])
 def test_cancel(self):
  jid=om.enqueue(self.c,1,'a','workspace_health','health-key-123')
  om.cancel(self.c,1,'a',jid)
  with self.assertRaises(ValueError):om.run_one(self.c,1,'a',jid)
 def test_validation(self):
  for kind,key in [('shell','health-key-123'),('workspace_health','short')]:
   with self.assertRaises(ValueError):om.enqueue(self.c,1,'a',kind,key)
 def test_readiness_and_guardian(self):
  for kind in ('workflow_readiness','guardian_summary'):
   jid=om.enqueue(self.c,1,'a',kind,kind+'-123');self.assertIsInstance(om.run_one(self.c,1,'a',jid),dict)
 def test_escape(self):
  om.enqueue(self.c,1,'a','workspace_health','<script>alert(1)</script>')
  page=om.render(self.c,1,'a','csrf');self.assertNotIn('<script>',page)
 def test_owner_recovery(self):
  jid=om.enqueue(self.c,1,'a','workspace_health','health-key-123')
  self.c.execute("UPDATE ov57_jobs SET status='failed',attempts=1 WHERE id=?",(jid,))
  self.access.return_value='editor'
  with self.assertRaises(ValueError):
   # mock access must actually enforce owner check
   with patch('sovereign_v56.access',side_effect=lambda c,u,w,**kw: (_ for _ in ()).throw(ValueError('owner')) if kw.get('owner') else 'editor'):
    om.recover(self.c,1,'a',jid)
  self.access.return_value='owner';om.recover(self.c,1,'a',jid)
  self.assertEqual(om.overview(self.c,1,'a')['counts']['queued'],1)
if __name__=='__main__':unittest.main()
