import io,sqlite3,unittest
import empire_v19 as empire
import sovereign_v56 as sv

class SovereignTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.c.execute('PRAGMA foreign_keys=ON')
  empire.setup(self.c);sv.setup(self.c)
  self.w=empire.create(self.c,1,'Alpha');self.other=empire.create(self.c,2,'Beta')
  self.csv=b'period,revenue,expenses,leads,customers\n2026-01,1000,400,100,20\n2026-02,800,500,100,10\n'
 def tearDown(self):self.c.close()
 def load(self):return sv.import_csv(self.c,1,self.w,'monthly.csv',self.csv)
 def test_import_and_evidence(self):
  iid=self.load();r=sv.report(self.c,1,self.w)
  self.assertEqual(len(r['facts']),2);self.assertEqual(len(r['opportunities']),3)
  self.assertEqual(r['facts'][0]['source_import_id'],iid)
 def test_duplicate_import(self):
  self.load()
  with self.assertRaises(ValueError):self.load()
 def test_cross_tenant_read_write(self):
  self.load()
  with self.assertRaises(ValueError):sv.report(self.c,2,self.w)
  with self.assertRaises(ValueError):sv.import_csv(self.c,2,self.w,'x.csv',self.csv)
  with self.assertRaises(ValueError):sv.propose(self.c,2,self.w,'revenue_decline:2026-02')
  self.assertEqual(sv.report(self.c,2,self.other)['facts'],[])
 def test_approval_and_outcome(self):
  self.load();aid=sv.propose(self.c,1,self.w,'revenue_decline:2026-02')
  with self.assertRaises(ValueError):sv.transition(self.c,2,self.w,aid,'approve')
  self.assertEqual(sv.transition(self.c,1,self.w,aid,'approve'),'approved')
  with self.assertRaises(ValueError):sv.transition(self.c,1,self.w,aid,'approve')
  with self.assertRaises(ValueError):sv.transition(self.c,1,self.w,aid,'complete','')
  self.assertEqual(sv.transition(self.c,1,self.w,aid,'complete','Investigated source data'),'completed')
  self.assertEqual(sv.report(self.c,1,self.w)['actions'][0]['outcome'],'Investigated source data')
 def test_viewer_no_write(self):
  self.c.execute('INSERT INTO empire_members VALUES(?,?,?)',(self.w,3,'viewer'))
  self.load();self.assertEqual(len(sv.report(self.c,3,self.w)['facts']),2)
  with self.assertRaises(ValueError):sv.propose(self.c,3,self.w,'revenue_decline:2026-02')
 def test_invalid_data_atomic(self):
  for data in (b'period,revenue,expenses,leads,customers\n2026-01,nan,2,3,1\n',b'period,revenue,expenses,leads,customers\n2026-01,5,2,3,1\n2026-02,4,3,2,9\n',b'period,revenue,expenses,leads,customers\n2026-01,1,2,3,1\n2026-01,2,2,3,1\n'):
   with self.assertRaises(ValueError):sv.import_csv(self.c,1,self.w,'bad.csv',data)
  self.assertEqual(self.c.execute('SELECT COUNT(*) FROM sv56_metrics').fetchone()[0],0)
 def test_scenarios(self):
  self.load();s=sv.simulate(self.c,1,self.w,10,-20)
  self.assertEqual(s['scenario']['revenue'],880)
  self.assertEqual(s['scenario']['expenses'],400)
  with self.assertRaises(ValueError):sv.simulate(self.c,1,self.w,float('nan'),0)
 def test_conflicting_periods(self):
  self.load();sv.import_csv(self.c,1,self.w,'another.csv',b'period,revenue,expenses,leads,customers\n2026-02,900,600,90,9\n')
  r=sv.report(self.c,1,self.w)
  self.assertEqual(r['conflicting_periods'],['2026-02']);self.assertEqual(len(r['facts']),1)
 def test_html_escaped(self):
  self.load();aid=sv.propose(self.c,1,self.w,'revenue_decline:2026-02');sv.transition(self.c,1,self.w,aid,'approve');sv.transition(self.c,1,self.w,aid,'complete','<script>alert(1)</script>')
  page=sv.render(self.c,1,'csrf',self.w)
  self.assertNotIn('<script>',page);self.assertIn('&lt;script&gt;',page)
 def test_audit(self):
  self.load();aid=sv.propose(self.c,1,self.w,'revenue_decline:2026-02');sv.transition(self.c,1,self.w,aid,'reject')
  self.assertEqual([x['event'] for x in sv.report(self.c,1,self.w)['audit']][:3],['action_rejected','action_proposed','csv_imported'])

if __name__=='__main__':unittest.main()
