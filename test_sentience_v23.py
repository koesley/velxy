import unittest,sqlite3,json
import empire_v19 as empire,genesis_prime_v20 as prime,autonomy_v22 as autonomy,sentience_v23 as sentience
class TestSentience(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:')
  for m in (empire,prime,autonomy,sentience):m.setup(self.c)
  self.a=empire.create(self.c,1,'Alpha');self.b=empire.create(self.c,2,'Bravo')
  self.app=prime.create(self.c,1,self.a,'Stock','inventory');prime.publish(self.c,1,self.a,self.app)
  prime.add_record(self.c,1,self.a,self.app,{'Item':'Shirt','Quantity':'3'})
 def tearDown(self):self.c.close()
 def test_isolation(self):
  self.assertEqual(sentience.overview(self.c,1,self.a)[0]['numeric_fields']['Quantity']['min'],3)
  with self.assertRaises(ValueError):sentience.overview(self.c,2,self.a)
  with self.assertRaises(ValueError):sentience.recommend(self.c,2,self.a,self.app,'Quantity',10)
 def test_approval(self):
  r=sentience.recommend(self.c,1,self.a,self.app,'Quantity',10)
  with self.assertRaises(ValueError):sentience.decide(self.c,2,self.a,r,True)
  rid=sentience.decide(self.c,1,self.a,r,True)
  self.assertEqual(autonomy.rule(self.c,1,self.a,rid)[6],'draft')
  with self.assertRaises(ValueError):sentience.decide(self.c,1,self.a,r,True)
 def test_reject(self):
  r=sentience.recommend(self.c,1,self.a,self.app,'Quantity',10)
  self.assertIsNone(sentience.decide(self.c,1,self.a,r,False))
  self.assertEqual(self.c.execute('SELECT COUNT(*) FROM autonomy_rules').fetchone()[0],0)
if __name__=='__main__':unittest.main()
