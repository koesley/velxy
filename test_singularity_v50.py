import unittest
from test_omniscience_v49 import OmniscienceTests
import singularity_v50 as singularity

class SingularityTests(OmniscienceTests):
 def test_empty_workspace_snapshot(self):
  r=singularity.report(self.c,1,self.w)
  self.assertEqual(r['workspace_id'],self.w)
  self.assertEqual(r['summary']['completed_experiments'],0)
 def test_approval_and_delivery_handoff(self):
  r=singularity.report(self.c,1,self.w)
  self.assertTrue(any(j['stage']=='delivery' for j in r['journeys']))
  self.make_step()
  r=singularity.report(self.c,1,self.w)
  self.assertTrue(any(j['milestones'] for j in r['journeys']))
 def test_cross_workspace_denied(self):
  with self.assertRaises(ValueError):singularity.report(self.c,2,self.w)
 def test_read_only(self):
  before=self.c.total_changes
  singularity.report(self.c,1,self.w)
  singularity.render(self.c,1,'csrf',self.w)
  self.assertEqual(before,self.c.total_changes)
 def test_json_serializable(self):
  import json
  self.assertIn('journeys',json.dumps(singularity.report(self.c,1,self.w),allow_nan=False))

if __name__=='__main__':unittest.main()
