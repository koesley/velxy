import sqlite3, unittest
import sovereign_command_v56 as cmd
class TestCommand(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:')
  self.c.execute('CREATE TABLE empire_members(workspace_id TEXT,user_id INTEGER,role TEXT)')
  self.c.execute("INSERT INTO empire_members VALUES('a',1,'owner')")
  self.c.execute("INSERT INTO empire_members VALUES('b',2,'owner')")
  self.c.execute('CREATE TABLE sv56_guardian_alerts(workspace_id TEXT,status TEXT)')
  self.c.executemany('INSERT INTO sv56_guardian_alerts VALUES(?,?)',[('a','open'),('a','resolved'),('b','open')])
 def tearDown(self):self.c.close()
 def test_intents(self):
  self.assertEqual(cmd.interpret('How many alerts?'),'alerts')
  self.assertEqual(cmd.interpret('Show connector sources'),'sources')
  self.assertEqual(cmd.interpret('How many strategies?'),'strategies')
  self.assertEqual(cmd.interpret('Show execution jobs'),'execution')
  self.assertEqual(cmd.interpret('Show memory decisions'),'memory')
  self.assertEqual(cmd.interpret('Show future simulations'),'future')
 def test_write_block(self):self.assertEqual(cmd.interpret('approve execution'),'blocked')
 def test_unsupported(self):self.assertEqual(cmd.interpret('weather today'),'unsupported')
 def test_ambiguous(self):self.assertEqual(cmd.interpret('alerts and strategies'),'ambiguous')
 def test_validation(self):
  for value in ('','x'*501,'hello\nworld'):
   with self.assertRaises(ValueError):cmd.interpret(value)
 def test_isolation(self):
  self.assertIn('2 Guardian alerts',cmd.answer(self.c,1,'a','alerts')['answer'])
  self.assertIn('1 currently open',cmd.answer(self.c,1,'a','alerts')['answer'])
  with self.assertRaises(ValueError):cmd.answer(self.c,1,'b','alerts')
 def test_no_table(self):self.assertIn('no available local table',cmd.answer(self.c,1,'a','strategies')['answer'])
 def test_escaping(self):
  html=cmd.render(self.c,1,'token','a','<script>alert(1)</script>')
  self.assertNotIn('<script>',html)
  self.assertIn('&lt;script&gt;',html)
 def test_read_only(self):
  before=self.c.total_changes
  cmd.answer(self.c,1,'a','How many alerts?')
  self.assertEqual(before,self.c.total_changes)
if __name__=='__main__':unittest.main()
