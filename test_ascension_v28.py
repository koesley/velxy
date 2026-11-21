"""Focused V28 tests. Run with python -m unittest test_ascension_v28."""
import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

class AscensionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  # Isolation, third attempt — the first two fixes each hit a different
  # fail-closed guard, and the lesson is: do NOT route this test through
  # portal.db() / persistent.connect() at all.
  #  * The Render build sets VELXTRIA_DATABASE_URL, so portal.db()
  #    connects to PRODUCTION Postgres and the setUp INSERT of user id 1
  #    fails with a UniqueViolation (id 1 is a real account) — every
  #    deploy fails and the live site is stuck.
  #  * Unsetting the URL is no good either: the build also sets
  #    VELXTRIA_REQUIRE_PERSISTENCE=1, and persistent.py raises at
  #    import ("Persistent mode requires VELXTRIA_DATABASE_URL") when the
  #    URL is empty, and persistent.connect() raises again ("Persistent
  #    storage is required") whenever REQUIRE is on and REMOTE is off.
  # So: keep the URL set (import stays happy), flip persistent.REMOTE
  # off AFTER import so _initialize_schema uses the sqlite DDL and sets
  # up the local modules, and open the temp sqlite file DIRECTLY with
  # sqlite3 — never through persistent.connect. empire_v19 and
  # ascension_v28 take the connection as an argument and never touch
  # portal.db(), so this isolated connection is all they need.
  self.env=patch.dict(os.environ,{'VELXTRIA_DATA_DIR':self.tmp.name,'VELXTRIA_LOCAL_STUDIO':'1','VELXTRIA_DEPLOYMENT_MODE':'local'})
  self.env.start()
  import portal,empire_v19,ascension_v28,persistent
  self.portal=portal;self.empire=empire_v19;self.asc=ascension_v28
  self.old_db=portal.DB
  self.old_remote=persistent.REMOTE
  persistent.REMOTE=False
  portal.DB=Path(self.tmp.name)/"portal.sqlite3"
  import sqlite3
  self.c=sqlite3.connect(str(portal.DB),timeout=15)
  self.c.execute('PRAGMA foreign_keys=ON')
  portal._initialize_schema(self.c)
  self.c.execute("INSERT INTO users(id,email,salt,pw_hash,role,access,created) VALUES(1,'one@example.test','a','b','customer','demo',0),(2,'two@example.test','a','b','customer','demo',0)")
  self.w1=self.empire.create(self.c,1,'Alpha <Workspace>');self.w2=self.empire.create(self.c,2,'Beta')
  self.c.commit()
 def tearDown(self):
  self.c.close();self.portal.DB=self.old_db
  import persistent;persistent.REMOTE=self.old_remote
  self.env.stop();self.tmp.cleanup()
 def test_workspace_scoping_and_escaping(self):
  page=self.asc.dashboard(self.c,1,self.w1)
  self.assertIn('Alpha &lt;Workspace&gt;',page)
  self.assertNotIn('Beta',page)
  self.assertIn('/oracle?w='+self.w1,page)
  with self.assertRaises(ValueError):self.asc.dashboard(self.c,1,self.w2)
 def test_onboarding_is_data_driven(self):
  page=self.asc.dashboard(self.c,1,self.w1)
  self.assertIn('0 of 3 requirements completed',page)
  self.assertIn('aria-valuenow="0"',page)
 def test_next_action_follows_evidence_order(self):
  evidence=[('Publish application',False,'/genesis-prime'),('Create record',False,'/genesis-prime'),('Set goal',False,'/nexus-intelligence')]
  with patch.object(self.asc.launchpad_v27,'evidence',return_value=evidence):
   page=self.asc.dashboard(self.c,1,self.w1)
  self.assertIn('RECOMMENDED NEXT ACTION',page)
  self.assertIn('Publish application',page)
  self.assertIn('href="/genesis-prime?w='+self.w1+'"',page)
  evidence[0]=('Publish application',True,'/genesis-prime')
  with patch.object(self.asc.launchpad_v27,'evidence',return_value=evidence):
   page=self.asc.dashboard(self.c,1,self.w1)
  self.assertIn('Create record</h2>',page)
  self.assertNotIn('Publish application</h2>',page)
 def test_completed_checklist_does_not_claim_production_ready(self):
  evidence=[('Published app',True,'/genesis-prime'),('Saved record',True,'/genesis-prime'),('Goal',True,'/nexus-intelligence')]
  with patch.object(self.asc.launchpad_v27,'evidence',return_value=evidence):
   page=self.asc.dashboard(self.c,1,self.w1)
  self.assertIn('Workspace checklist complete',page)
  self.assertIn('3 of 3 requirements completed',page)
  self.assertIn('before treating the workspace as customer-ready',page)
 def test_untrusted_evidence_is_escaped(self):
  evidence=[('<img src=x onerror=alert(1)>',False,'/genesis-prime')]
  with patch.object(self.asc.launchpad_v27,'evidence',return_value=evidence):
   page=self.asc.dashboard(self.c,1,self.w1)
  self.assertNotIn('<img src=x',page)
  self.assertIn('&lt;img src=x',page)
 def test_no_cross_workspace_data_in_action_panel(self):
  with patch.object(self.asc.launchpad_v27,'evidence',return_value=[('Private Alpha task',False,'/genesis-prime')]):
   page=self.asc.dashboard(self.c,1,self.w1)
  self.assertIn('Private Alpha task',page)
  with self.assertRaises(ValueError):
   self.asc.dashboard(self.c,1,self.w2)
 def test_action_link_rejects_untrusted_destinations(self):
  for path in ('https://evil.example','//evil.example','javascript:alert(1)','/unknown','/oracle" onclick="alert(1)'):
   with self.subTest(path=path):
    with self.assertRaises(ValueError):self.asc.route_url(path,self.w1)
 def test_workspace_query_is_encoded_in_links(self):
  url=self.asc.route_url('/oracle','a&b"<c')
  self.assertIn('w=a%26b%22%3Cc',url)
  self.assertNotIn('"<c',url)
 def test_evidence_with_untrusted_route_is_rejected(self):
  with patch.object(self.asc.launchpad_v27,'evidence',return_value=[('Untrusted',False,'https://evil.example')]):
   with self.assertRaises(ValueError):self.asc.dashboard(self.c,1,self.w1)
 def test_no_mutation(self):
  before=self.c.total_changes
  self.asc.dashboard(self.c,1,self.w1)
  self.assertEqual(before,self.c.total_changes)

if __name__=='__main__':unittest.main()
