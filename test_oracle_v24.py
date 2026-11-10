import sqlite3,unittest
import empire_v19,genesis_prime_v20 as prime,sentience_v23,autonomy_v22,oracle_v24
class OracleTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:')
  for mod in (empire_v19,prime,autonomy_v22,sentience_v23,oracle_v24):mod.setup(self.c)
  self.a=empire_v19.create(self.c,1,'Business A');self.b=empire_v19.create(self.c,2,'Business B')
  for uid,wid,qty in ((1,self.a,3),(2,self.b,999)):
   aid=prime.create(self.c,uid,wid,'Inventory','inventory');prime.publish(self.c,uid,wid,aid)
   prime.add_record(self.c,uid,wid,aid,{'Item':'shirt','Quantity':str(qty)})
 def tearDown(self):self.c.close()
 def test_tenant_isolation(self):
  ans=oracle_v24.answer(self.c,1,self.a,'inventory quantities')
  self.assertIn('3.0',ans);self.assertNotIn('999',ans)
  with self.assertRaises(ValueError):oracle_v24.answer(self.c,1,self.b,'inventory')
 def test_history_private(self):
  empire_v19.accept(self.c,3,empire_v19.invite(self.c,1,self.a,'viewer'))
  oracle_v24.answer(self.c,1,self.a,'inventory')
  page=oracle_v24.render(self.c,3,'csrf',self.a)
  self.assertNotIn('Inventory: 1 most recent records',page)
  self.assertEqual(self.c.execute('SELECT COUNT(*) FROM oracle_history WHERE user_id=1').fetchone()[0],1)
 def test_no_mutations(self):
  before=self.c.execute('SELECT COUNT(*) FROM autonomy_rules').fetchone()[0]
  oracle_v24.answer(self.c,1,self.a,'Please create a workflow')
  self.assertEqual(self.c.execute('SELECT COUNT(*) FROM autonomy_rules').fetchone()[0],before)
if __name__=='__main__':unittest.main()
