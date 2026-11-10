import sqlite3,unittest
from unittest.mock import patch
import sovereign_workflows_v56 as wf
class PlusTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.a=patch.object(wf.core,'access',return_value='owner');self.b=patch.object(wf.core,'audit');self.a.start();self.b.start()
 def tearDown(self):self.a.stop();self.b.stop();self.c.close()
 def test_templates(self):
  for key in ('launch','resilience'):
   x=wf.create(self.c,1,'a','Plan '+key,key);self.assertTrue(wf.overview(self.c,1,'a')['workflows'])
 def test_duplicate(self):
  x=wf.create(self.c,1,'a','Original plan','discover');wf.update(self.c,1,'a',x,'approve');wf.update(self.c,1,'a',x,'duplicate')
  self.assertEqual(sorted(z['status'] for z in wf.overview(self.c,1,'a')['workflows']),['approved','draft'])
 def test_note_scope_and_escape(self):
  x=wf.create(self.c,1,'a','Original plan','discover');wf.add_note(self.c,1,'a',x,'<script>alert(1)</script>')
  self.assertEqual(wf.overview(self.c,1,'b')['workflows'],[])
  self.assertNotIn('<script>',wf.render(self.c,1,'a','csrf'))
  with self.assertRaises(ValueError):wf.add_note(self.c,1,'b',x,'wrong scope')
 def test_note_validation(self):
  x=wf.create(self.c,1,'a','Original plan','discover')
  for bad in ('', 'x'*1001):
   with self.assertRaises(ValueError):wf.add_note(self.c,1,'a',x,bad)
 def test_readiness(self):
  x=wf.create(self.c,1,'a','Original plan','discover');wf.update(self.c,1,'a',x,'remove','approval')
  self.assertFalse(wf.overview(self.c,1,'a')['workflows'][0]['readiness']['can_approve'])
if __name__=='__main__':unittest.main()
