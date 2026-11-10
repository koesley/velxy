import unittest
from test_hyperion_v47 import HyperionTests
import quantum_command_v48 as q
class QuantumTests(HyperionTests):
 def setUp(self):
  super().setUp();q.setup(self.c)
 def tearDown(self):super().tearDown()
 def test_scenarios_and_missing(self):
  pid=self.h.create_plan(self.c,1,self.w,self.eid,'Quarterly operations','2027-03-01');sid=self.h.add_step(self.c,1,self.w,pid,'Review baseline','Review existing business data','2027-01-01')
  r=q.report(self.c,1,self.w);self.assertEqual(r['summary']['unestimated_milestones'],1)
  q.set_estimate(self.c,1,self.w,sid,80);q.set_capacity(self.c,1,self.w,20);r=q.report(self.c,1,self.w)
  self.assertEqual(r['scenarios']['baseline']['minimum_capacity_weeks'],4);self.assertEqual(r['scenarios']['conservative']['minimum_capacity_weeks'],8)
 def test_tenant_security(self):
  pid=self.h.create_plan(self.c,1,self.w,self.eid,'Quarterly operations','2027-03-01');sid=self.h.add_step(self.c,1,self.w,pid,'Review baseline','Review existing business data','2027-01-01')
  with self.assertRaises(ValueError):q.report(self.c,2,self.w)
  with self.assertRaises(ValueError):q.set_estimate(self.c,2,self.w,sid,8)
 def test_validation_and_immutability(self):
  pid=self.h.create_plan(self.c,1,self.w,self.eid,'Quarterly operations','2027-03-01');sid=self.h.add_step(self.c,1,self.w,pid,'Review baseline','Review existing business data','2027-01-01')
  for value in ('nan','inf','-1','0','10001','invalid'):
   with self.assertRaises(ValueError):q.set_estimate(self.c,1,self.w,sid,value)
  self.h.transition(self.c,1,self.w,sid,'done','Verified the full baseline')
  with self.assertRaises(ValueError):q.set_estimate(self.c,1,self.w,sid,4)
 def test_read_only_and_escaping(self):
  pid=self.h.create_plan(self.c,1,self.w,self.eid,'<script>alert(1)</script>','2027-03-01');before=self.c.total_changes;q.report(self.c,1,self.w);self.assertEqual(before,self.c.total_changes)
  page=q.render(self.c,1,'csrf',self.w);self.assertIn('&lt;script&gt;',page);self.assertNotIn('<script>alert(1)</script>',page)
 def test_dependency_critical_chain(self):
  pid=self.h.create_plan(self.c,1,self.w,self.eid,'Quarterly operations','2027-03-01');a=self.h.add_step(self.c,1,self.w,pid,'First stage','Review business data first','2027-01-01');b=self.h.add_step(self.c,1,self.w,pid,'Second stage','Review business data next','2027-02-01',a)
  q.set_estimate(self.c,1,self.w,a,8);q.set_estimate(self.c,1,self.w,b,12);self.assertEqual(q.report(self.c,1,self.w)['scenarios']['baseline']['critical_chain_hours'],20)
