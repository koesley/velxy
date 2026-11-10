import unittest,sqlite3
import empire_v19 as empire,genesis_prime_v20 as prime,nexus_v25 as nexus
class NexusTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:')
  for mod in (empire,prime,nexus):mod.setup(self.c)
  self.a=empire.create(self.c,1,'Alpha Business');self.b=empire.create(self.c,2,'Beta Business')
  self.app=prime.create(self.c,1,self.a,'Inventory','inventory');prime.publish(self.c,1,self.a,self.app)
  prime.add_record(self.c,1,self.a,self.app,{'Item':'Tshirt','Quantity':'3'})
  prime.add_record(self.c,1,self.a,self.app,{'Item':'Hoodie','Quantity':'11'})
  self.g=nexus.create_goal(self.c,1,self.a,self.app,'Reduce low stock','below_threshold','Quantity','0','10')
 def tearDown(self):self.c.close()
 def test_measure_snapshot_and_strategy(self):
  self.assertEqual(nexus.measure(self.c,1,self.a,self.g)['value'],1)
  nexus.measure(self.c,1,self.a,self.g,True)
  sid=nexus.propose(self.c,1,self.a,self.g)
  nexus.decide(self.c,1,self.a,sid,True)
  self.assertEqual(self.c.execute('SELECT status FROM nexus_strategies WHERE id=?',(sid,)).fetchone()[0],'approved')
  self.assertEqual(self.c.execute('SELECT count(*) FROM autonomy_rules').fetchone()[0],0) if self.c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='autonomy_rules'").fetchone() else None
 def test_cross_workspace_blocked(self):
  for action in (lambda:nexus.measure(self.c,2,self.b,self.g),lambda:nexus.propose(self.c,2,self.b,self.g),lambda:nexus.create_goal(self.c,2,self.b,self.app,'Wrong tenant','record_count','','1')):
   with self.assertRaises(ValueError):action()
 def test_permissions_and_validation(self):
  self.c.execute('INSERT INTO empire_members VALUES(?,?,?)',(self.a,3,'viewer'))
  self.assertEqual(nexus.measure(self.c,3,self.a,self.g)['value'],1)
  with self.assertRaises(ValueError):nexus.measure(self.c,3,self.a,self.g,True)
  with self.assertRaises(ValueError):nexus.propose(self.c,3,self.a,self.g)
  with self.assertRaises(ValueError):nexus.create_goal(self.c,1,self.a,self.app,'bad','numeric_average','Quantity','nan')
  sid=nexus.propose(self.c,1,self.a,self.g)
  with self.assertRaises(ValueError):nexus.decide(self.c,3,self.a,sid,True)
  nexus.decide(self.c,1,self.a,sid,False)
  with self.assertRaises(ValueError):nexus.decide(self.c,1,self.a,sid,True)
if __name__=='__main__':unittest.main()
