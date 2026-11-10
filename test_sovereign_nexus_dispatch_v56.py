import datetime,sqlite3,unittest
from unittest.mock import patch
import sovereign_nexus_v56 as nx
import sovereign_workflows_v56 as wf

class DispatchTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:')
  self.audit=patch('sovereign_v56.audit').start()
  self.access=patch('sovereign_v56.access',return_value='owner').start()
  self.w=wf.create(self.c,1,'one','Test','discover')
  wf.update(self.c,1,'one',self.w,'approve')
  future=(datetime.datetime.now()+datetime.timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
  self.sid=nx.plan_schedule(self.c,1,'one',self.w,future)
 def tearDown(self):patch.stopall();self.c.close()
 def due(self):
  self.c.execute('UPDATE sv56_nexus_schedules SET run_at=? WHERE id=?',((datetime.datetime.now()-datetime.timedelta(minutes=2)).strftime('%Y-%m-%dT%H:%M'),self.sid));self.c.commit()
 def test_not_before_due(self):
  with self.assertRaisesRegex(ValueError,'not arrived'):nx.dispatch_due(self.c,1,'one',self.sid)
 def test_dispatch_once_and_scoped(self):
  self.due()
  self.assertEqual(len(nx.due_queue(self.c,1,'one')),1)
  self.assertEqual(nx.due_queue(self.c,1,'other'),[])
  with self.assertRaises(ValueError):nx.dispatch_due(self.c,1,'other',self.sid)
  rid=nx.dispatch_due(self.c,1,'one',self.sid)
  self.assertEqual(nx.dispatch_due(self.c,1,'one',self.sid),rid)
  self.assertEqual(self.c.execute('SELECT count(*) FROM sv56_workflow_runs').fetchone()[0],1)
  self.assertEqual(nx.advanced_overview(self.c,1,'one')['schedules'][0]['status'],'dispatched')
  self.assertEqual(len(nx.advanced_overview(self.c,1,'one')['dispatches']),1)
 def test_cancelled_not_dispatchable(self):
  self.due();nx.cancel_schedule(self.c,1,'one',self.sid)
  with self.assertRaises(ValueError):nx.dispatch_due(self.c,1,'one',self.sid)
 def test_rechecks_blueprint(self):
  self.due()
  self.c.execute("UPDATE sv56_workflows SET status='draft' WHERE id=?",(self.w,))
  with self.assertRaises(ValueError):nx.dispatch_due(self.c,1,'one',self.sid)
  self.assertEqual(self.c.execute('SELECT count(*) FROM sv56_nexus_dispatches').fetchone()[0],0)
if __name__=='__main__':unittest.main()
