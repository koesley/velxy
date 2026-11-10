import sqlite3,unittest
import empire_v19,genesis_prime_v20,nexus_v25,launchpad_v27

class LaunchpadTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');empire_v19.setup(self.c);genesis_prime_v20.setup(self.c);nexus_v25.setup(self.c);launchpad_v27.setup(self.c)
  self.w=empire_v19.create(self.c,1,'Business A');self.other=empire_v19.create(self.c,2,'Business B')
  self.c.execute('INSERT INTO empire_members VALUES(?,?,?)',(self.w,3,'viewer'))
  self.c.execute('INSERT INTO empire_members VALUES(?,?,?)',(self.w,4,'editor'))
 def tearDown(self):self.c.close()
 def test_isolation_and_roles(self):
  p=launchpad_v27.create(self.c,1,self.w,'First pilot')
  with self.assertRaises(ValueError):launchpad_v27.feedback(self.c,2,self.w,p,5,'Good test')
  with self.assertRaises(ValueError):launchpad_v27.create(self.c,3,self.w,'Viewer pilot')
  with self.assertRaises(ValueError):launchpad_v27.finish(self.c,2,self.other,p)
  self.assertNotIn('First pilot',launchpad_v27.render(self.c,2,'csrf',self.other))
 def test_feedback_and_safe_html(self):
  p=launchpad_v27.create(self.c,4,self.w,'<script>bad</script>')
  launchpad_v27.feedback(self.c,4,self.w,p,4,'<img src=x onerror=alert(1)>')
  page=launchpad_v27.render(self.c,1,'csrf',self.w)
  self.assertNotIn('<script>',page);self.assertNotIn('<img',page)
  with self.assertRaises(ValueError):launchpad_v27.feedback(self.c,4,self.w,p,6,'Bad rating')
 def test_completion_requires_real_evidence(self):
  p=launchpad_v27.create(self.c,1,self.w,'Completion test')
  launchpad_v27.feedback(self.c,1,self.w,p,5,'Trial works')
  with self.assertRaises(ValueError):launchpad_v27.finish(self.c,1,self.w,p)
  self.c.execute("INSERT INTO prime_apps VALUES(?,?,?,?,?,?,?,?)",('a',self.w,'Demo','{}','published',1,1,1))
  self.c.execute("INSERT INTO prime_records VALUES(?,?,?,?,?,?)",('r','a',self.w,'{}',1,1))
  self.c.execute("INSERT INTO nexus_goals VALUES(?,?,?,?,?,?,?,?,?,?)",('g',self.w,'a','count','',0,1,'Goal',1,1))
  launchpad_v27.finish(self.c,1,self.w,p)
  self.assertEqual(self.c.execute('SELECT status FROM launchpad_pilots WHERE id=?',(p,)).fetchone()[0],'completed')
if __name__=='__main__':unittest.main()
