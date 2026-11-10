import sqlite3,unittest
from unittest.mock import patch
import empire_v19,genesis_prime_v20 as prime,architect_v21 as a
class ArchitectTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');empire_v19.setup(self.c);prime.setup(self.c);a.setup(self.c)
  self.w1=empire_v19.create(self.c,1,'Business One');self.w2=empire_v19.create(self.c,2,'Business Two')
 def tearDown(self):self.c.close()
 def test_tenant_isolation_and_owner_approval(self):
  with patch.object(a,'suggest',return_value=('Inventory',[{'name':'SKU','type':'text','required':True}])):
   pid=a.propose(self.c,1,self.w1,'Make inventory application')
  with self.assertRaises(ValueError):a.approve(self.c,2,self.w2,pid)
  aid=a.approve(self.c,1,self.w1,pid)
  self.assertEqual(prime.app(self.c,1,self.w1,aid)[3],'draft')
  with self.assertRaises(ValueError):prime.app(self.c,2,self.w2,aid)
  with self.assertRaises(ValueError):a.approve(self.c,1,self.w1,pid)
 def test_revision_and_rejection(self):
  aid=prime.create(self.c,1,self.w1,'CRM','crm')
  with patch.object(a,'suggest',return_value=('CRM',[{'name':'Contact','type':'text','required':True}])):
   pid=a.propose(self.c,1,self.w1,'Make contact field required',aid)
  a.reject(self.c,1,self.w1,pid)
  with self.assertRaises(ValueError):a.approve(self.c,1,self.w1,pid)
  self.assertEqual(prime.app(self.c,1,self.w1,aid)[4],1)
 def test_invalid_schema(self):
  with self.assertRaises(ValueError):prime.schema_check([{'name':'X','type':'python','required':True}])
if __name__=='__main__':unittest.main()
