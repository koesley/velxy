import sqlite3,unittest
import empire_v19 as e,genesis_prime_v20 as g
class PrimeTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.c.execute('CREATE TABLE users(id INTEGER PRIMARY KEY,email TEXT)')
  for i in range(1,6):self.c.execute('INSERT INTO users VALUES(?,?)',(i,f'u{i}@test.local'))
  e.setup(self.c);g.setup(self.c)
  self.a=e.create(self.c,1,'Business A');self.b=e.create(self.c,2,'Business B')
  self.editor=e.invite(self.c,1,self.a,'editor');e.accept(self.c,3,self.editor)
  self.viewer=e.invite(self.c,1,self.a,'viewer');e.accept(self.c,4,self.viewer)
 def test_isolation(self):
  aid=g.create(self.c,1,self.a,'Stock','inventory')
  for uid,wid in [(2,self.b),(2,self.a),(4,self.b)]:
   with self.assertRaises(ValueError):g.app(self.c,uid,wid,aid)
   with self.assertRaises(ValueError):g.add_field(self.c,uid,wid,aid,'Other','text',False)
  with self.assertRaises(ValueError):g.app(self.c,4,self.a,aid,True)
 def test_publish_permissions_and_records(self):
  aid=g.create(self.c,3,self.a,'Stock','inventory')
  g.add_field(self.c,3,self.a,aid,'Category','text',False)
  with self.assertRaises(ValueError):g.publish(self.c,3,self.a,aid)
  with self.assertRaises(ValueError):g.add_record(self.c,1,self.a,aid,{'Item':'A','Quantity':'2','Category':''})
  g.publish(self.c,1,self.a,aid)
  rid=g.add_record(self.c,3,self.a,aid,{'Item':'A','Quantity':'2','Category':''})
  with self.assertRaises(ValueError):g.add_record(self.c,2,self.b,aid,{'Item':'A','Quantity':'2','Category':''})
  with self.assertRaises(ValueError):g.delete_record(self.c,4,self.a,aid,rid)
  self.assertIn('Item: A',g.render(self.c,4,'csrf',self.a,aid))
  self.assertNotIn('Item: A',g.render(self.c,2,'csrf',self.b))
  g.delete_record(self.c,1,self.a,aid,rid)
 def test_schema_validation(self):
  with self.assertRaises(ValueError):g.schema_check([{'name':'X','type':'text','required':True},{'name':'x','type':'text','required':False}])
  with self.assertRaises(ValueError):g.schema_check([{'name':'x','type':'python','required':False}])
  aid=g.create(self.c,1,self.a,'Calendar','appointments');g.publish(self.c,1,self.a,aid)
  with self.assertRaises(ValueError):g.add_record(self.c,1,self.a,aid,{'Customer':'Jane','Date':'2026-99-99'})
if __name__=='__main__':unittest.main()
