import datetime
import unittest
from test_quantum_command_v48 import QuantumTests
import omniscience_v49 as omni
import quantum_command_v48 as quantum

class OmniscienceTests(QuantumTests):
 def setUp(self):
  super().setUp();omni.setup(self.c)
 def make_step(self):
  pid=self.h.create_plan(self.c,1,self.w,self.eid,'Performance improvement plan','2027-03-01')
  sid=self.h.add_step(self.c,1,self.w,pid,'Measure processing','Measure time for business processing','2027-02-01')
  quantum.set_estimate(self.c,1,self.w,sid,8)
  return pid,sid
 def log(self,sid,hours=2,note='Performed verified work today'):
  return omni.log_effort(self.c,1,self.w,sid,hours,datetime.date.today().isoformat(),note)
 def test_actual_and_variance(self):
  _,sid=self.make_step();self.log(sid,3);self.log(sid,2)
  r=omni.report(self.c,1,self.w);step=r['plans'][0]['steps'][0]
  self.assertEqual(step['actual_hours'],5);self.assertEqual(step['variance_hours'],-3)
  self.assertEqual(r['summary']['open_remaining_estimated_hours'],3)
 def test_tenant_access_and_wrong_step(self):
  _,sid=self.make_step()
  with self.assertRaises(ValueError):omni.report(self.c,2,self.w)
  with self.assertRaises(ValueError):omni.log_effort(self.c,2,self.w,sid,2,datetime.date.today().isoformat(),'Valid work evidence')
  with self.assertRaises(ValueError):omni.log_effort(self.c,1,self.w,'wrong-step',2,datetime.date.today().isoformat(),'Valid work evidence')
 def test_validation_and_no_future(self):
  _,sid=self.make_step()
  for bad in ('nan','inf','-1','0','25','oops'):
   with self.assertRaises(ValueError):self.log(sid,bad)
  future=(datetime.date.today()+datetime.timedelta(days=1)).isoformat()
  with self.assertRaises(ValueError):omni.log_effort(self.c,1,self.w,sid,2,future,'Valid work evidence')
  with self.assertRaises(ValueError):self.log(sid,2,'short')
 def test_read_only_and_escaping(self):
  _,sid=self.make_step();self.log(sid,2,'<script>alert(1)</script> performed')
  before=self.c.total_changes
  r=omni.report(self.c,1,self.w);page=omni.render(self.c,1,'csrf',self.w)
  self.assertEqual(before,self.c.total_changes)
  self.assertIn('&lt;script&gt;',page);self.assertNotIn('<script>',page)
  self.assertEqual(len(r['history']),1)
 def test_historical_calibration_only_after_three(self):
  pid=self.h.create_plan(self.c,1,self.w,self.eid,'Operational capacity review','2027-03-01')
  for i in range(3):
   sid=self.h.add_step(self.c,1,self.w,pid,'Completed phase '+str(i),'Perform measurable business work','2027-02-01')
   quantum.set_estimate(self.c,1,self.w,sid,2)
   self.log(sid,4)
   self.h.transition(self.c,1,self.w,sid,'done','Verified completion of business work')
  open_sid=self.h.add_step(self.c,1,self.w,pid,'Upcoming phase','Perform measurable upcoming work','2027-02-01')
  quantum.set_estimate(self.c,1,self.w,open_sid,10)
  r=omni.report(self.c,1,self.w)
  self.assertTrue(r['summary']['historical_adjustment_applied'])
  self.assertEqual(r['summary']['median_actual_to_estimate_ratio'],2)
  self.assertEqual(r['summary']['historically_adjusted_open_hours'],20)
 def test_closed_plan_blocks_log(self):
  pid,sid=self.make_step();self.h.transition(self.c,1,self.w,sid,'done','Verified milestone completion evidence');self.h.close_plan(self.c,1,self.w,pid)
  with self.assertRaises(ValueError):self.log(sid)

if __name__=='__main__':unittest.main()
