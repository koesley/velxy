import unittest
from test_sovereign_connectors_v56 import ConnectorTests
import sovereign_connectors_v56 as connectors
import sovereign_guardian_v56 as guardian

class GuardianTests(ConnectorTests):
 def setUp(self):
  super().setUp();guardian.setup(self.c)
 def seed(self):
  sid=connectors.create_source(self.c,1,self.w,'Guardian source')
  csv=b'external_id,period,revenue,expenses,leads,customers\na,2026-01,1000,200,10,2\nb,2026-02,500,700,10,2\n'
  connectors.apply(self.c,1,self.w,connectors.ingest(self.c,1,self.w,sid,'g.csv',csv))
  return sid
 def test_scan_and_deduplication(self):
  self.seed();result=guardian.evaluate(self.c,1,self.w)
  self.assertGreaterEqual(result['findings'],2)
  alerts=guardian.history(self.c,1,self.w)['alerts'];self.assertIn('revenue_drop',{a['rule'] for a in alerts})
  guardian.evaluate(self.c,1,self.w)
  self.assertEqual(len(alerts),len(guardian.history(self.c,1,self.w)['alerts']))
 def test_lifecycle_and_history(self):
  self.seed();guardian.evaluate(self.c,1,self.w)
  aid=guardian.history(self.c,1,self.w)['alerts'][0]['id']
  guardian.update_status(self.c,1,self.w,aid,'acknowledged')
  guardian.evaluate(self.c,1,self.w)
  self.assertEqual(next(a for a in guardian.history(self.c,1,self.w)['alerts'] if a['id']==aid)['status'],'acknowledged')
  guardian.update_status(self.c,1,self.w,aid,'resolved')
  self.assertTrue(guardian.history(self.c,1,self.w)['events'])
 def test_permission_and_scope(self):
  self.seed()
  with self.assertRaises(ValueError):guardian.evaluate(self.c,2,self.w)
  with self.assertRaises(ValueError):guardian.history(self.c,2,self.w)
  guardian.evaluate(self.c,1,self.w)
  aid=guardian.history(self.c,1,self.w)['alerts'][0]['id']
  with self.assertRaises(ValueError):guardian.update_status(self.c,2,self.w,aid,'resolved')
  with self.assertRaises(ValueError):guardian.update_status(self.c,1,self.w,aid,'invalid')
  with self.assertRaises(ValueError):guardian.update_status(self.c,1,self.w,'not-an-alert','resolved')
 def test_no_approved_data(self):
  result=guardian.evaluate(self.c,1,self.w)
  self.assertEqual(result['findings'],0)
 def test_html_escaping(self):
  self.seed();guardian.evaluate(self.c,1,self.w)
  page=guardian.render(self.c,1,'<csrf>',self.w)
  self.assertNotIn('value="<csrf>"',page)
  self.assertIn('Business Guardian',page)

if __name__=='__main__':unittest.main()
