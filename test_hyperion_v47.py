import unittest
from test_synapse_v44 import SynapseTests
class HyperionTests(unittest.TestCase):
 def setUp(self):
  SynapseTests.setUp(self)
  import hyperion_v47 as h
  self.h=h;self.approve()
 def tearDown(self):SynapseTests.tearDown(self)
 def approve(self):SynapseTests.approve(self)
 def plan(self):return self.h.create_plan(self.c,1,self.w,self.eid,'Quarterly operations','2027-03-01')
 def test_dependencies_and_evidence(self):
  pid=self.plan();a=self.h.add_step(self.c,1,self.w,pid,'Collect baseline','Review the baseline records','2027-01-01');b=self.h.add_step(self.c,1,self.w,pid,'Analyze results','Compare the business records','2027-02-01',a)
  with self.assertRaises(ValueError):self.h.transition(self.c,1,self.w,b,'doing')
  with self.assertRaises(ValueError):self.h.transition(self.c,1,self.w,a,'done','short')
  self.h.transition(self.c,1,self.w,a,'done','Verified the initial records')
  self.h.transition(self.c,1,self.w,b,'doing');self.h.transition(self.c,1,self.w,b,'done','Compared every record available')
  self.h.close_plan(self.c,1,self.w,pid)
  with self.assertRaises(ValueError):self.h.transition(self.c,1,self.w,a,'cancelled')
 def test_scope_and_dates(self):
  pid=self.plan()
  with self.assertRaises(ValueError):self.h.report(self.c,2,self.w)
  with self.assertRaises(ValueError):self.h.add_step(self.c,2,self.w,pid,'Steal data','Attempt to cross tenant','2027-02-01')
  with self.assertRaises(ValueError):self.h.add_step(self.c,1,self.w,pid,'Invalid date','Review the business data','2027-02-31')
 def test_risk_and_readonly(self):
  pid=self.plan();self.h.add_step(self.c,1,self.w,pid,'Overdue work','Review records manually','2020-01-01');n=self.c.total_changes;r=self.h.report(self.c,1,self.w);self.assertEqual(n,self.c.total_changes);self.assertEqual(r['summary']['overdue'],1)
  with self.assertRaises(ValueError):self.h.close_plan(self.c,1,self.w,pid)
 def test_html_escape(self):
  pid=self.h.create_plan(self.c,1,self.w,self.eid,'<script>bad</script>','2027-03-01');page=self.h.render(self.c,1,'csrf',self.w);self.assertIn('&lt;script&gt;',page);self.assertNotIn('<script>bad</script>',page)
 def test_no_record_mutation(self):
  n=self.c.execute('SELECT count(*) FROM prime_records').fetchone()[0];pid=self.plan();self.h.add_step(self.c,1,self.w,pid,'Review records','Review records manually','2027-01-01');self.assertEqual(n,self.c.execute('SELECT count(*) FROM prime_records').fetchone()[0])
