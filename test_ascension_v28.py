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
 def test_every_navigation_link_encodes_workspace(self):
  from unittest.mock import patch
  wid='alpha&evil="onmouseover'
  original=self.w1
  with patch.object(self.asc.foundation_v26,'workspaces',return_value=[(wid,'Unsafe name')]), patch.object(self.asc.empire_v19,'role',return_value='owner'), patch.object(self.asc.foundation_v26,'overview',return_value={}), patch.object(self.asc.launchpad_v27,'evidence',return_value=[('Done',True,'/genesis-prime')]):
   # The dashboard's pilot queries remain scoped to this artificial workspace.
   page=self.asc.dashboard(self.c,1,wid)
  self.assertNotIn('w='+wid,page)
  self.assertIn('w=alpha%26evil%3D%22onmouseover',page)
  self.assertNotIn('href="/launchpad?w=alpha&',page)
  self.assertNotIn('href="/genesis-prime?w=alpha&',page)
 def test_pilot_outcomes_are_real_and_workspace_scoped(self):
  import launchpad_v27
  pid=launchpad_v27.create(self.c,1,self.w1,'Alpha customer trial')
  launchpad_v27.feedback(self.c,1,self.w1,pid,4,'Useful pilot feedback')
  other=launchpad_v27.create(self.c,2,self.w2,'Beta customer trial')
  launchpad_v27.feedback(self.c,2,self.w2,other,1,'Private beta feedback')
  page=self.asc.dashboard(self.c,1,self.w1)
  self.assertIn('Real pilot outcomes',page)
  self.assertIn('Average pilot rating',page)
  self.assertIn('4.0 / 5',page)
  self.assertNotIn('1.0 / 5',page)
  self.assertNotIn('Private beta feedback',page)
 def test_low_rating_alert_is_evidence_based_and_tenant_scoped(self):
  import launchpad_v27
  alpha=launchpad_v27.create(self.c,1,self.w1,'Alpha trial')
  beta=launchpad_v27.create(self.c,2,self.w2,'Beta trial')
  launchpad_v27.feedback(self.c,2,self.w2,beta,1,'Very poor experience')
  page=self.asc.dashboard(self.c,1,self.w1)
  self.assertNotIn('Customer feedback needs attention',page)
  launchpad_v27.feedback(self.c,1,self.w1,alpha,2,'Needs improvement')
  page=self.asc.dashboard(self.c,1,self.w1)
  self.assertIn('Customer feedback needs attention',page)
  self.assertIn('1 rating(s) of 2/5 or lower',page)
  self.assertIn('href="/launchpad?w='+self.w1+'"',page)
  self.assertNotIn('Very poor experience',page)
 def test_customer_risk_outweighs_onboarding_next_action(self):
  import launchpad_v27
  pilot=launchpad_v27.create(self.c,1,self.w1,'Priority trial')
  launchpad_v27.feedback(self.c,1,self.w1,pilot,1,'Unresolved customer issue')
  page=self.asc.dashboard(self.c,1,self.w1)
  self.assertIn('PRIORITY CUSTOMER RISK',page)
  self.assertIn('Review low-rated customer feedback</h2>',page)
  self.assertNotIn('Published business application</h2>',page)
  self.assertIn('href="/launchpad?w='+self.w1+'"',page)
 def test_other_workspace_risk_cannot_change_recommendation(self):
  import launchpad_v27
  pilot=launchpad_v27.create(self.c,2,self.w2,'Other trial')
  launchpad_v27.feedback(self.c,2,self.w2,pilot,1,'Unresolved other issue')
  page=self.asc.dashboard(self.c,1,self.w1)
  self.assertNotIn('PRIORITY CUSTOMER RISK',page)
  self.assertIn('Published business application</h2>',page)
 def test_good_feedback_does_not_trigger_risk_alert(self):
  import launchpad_v27
  pilot=launchpad_v27.create(self.c,1,self.w1,'Alpha trial')
  launchpad_v27.feedback(self.c,1,self.w1,pilot,5,'Excellent experience')
  page=self.asc.dashboard(self.c,1,self.w1)
  self.assertIn('No ratings of 2/5 or lower',page)
  self.assertNotIn('Customer feedback needs attention',page)
 def test_empty_pilot_outcomes_are_not_invented(self):
  page=self.asc.dashboard(self.c,1,self.w1)
  self.assertIn('No ratings yet',page)
  self.assertIn('Customer pilot outcomes',page)
 def test_launchpad_feedback_count_is_not_capped_at_visible_limit(self):
  import launchpad_v27
  pilot=launchpad_v27.create(self.c,1,self.w1,'Long running pilot')
  for index in range(31):
   launchpad_v27.feedback(self.c,1,self.w1,pilot,4,'Feedback entry '+str(index))
  page=launchpad_v27.render(self.c,1,'csrf-test',self.w1)
  self.assertIn('Feedback entries: 31',page)
 def test_launchpad_tool_urls_are_encoded_and_allowlisted(self):
  import launchpad_v27
  self.assertIn('w=a%26b%22',launchpad_v27.tool_url('/genesis-prime','a&b"'))
  for path in ('https://malicious.example','//malicious.example','javascript:alert(1)','/oracle'):
   with self.subTest(path=path):
    with self.assertRaises(ValueError):
     launchpad_v27.tool_url(path,self.w1)
 def test_no_mutation(self):
  before=self.c.total_changes
  self.asc.dashboard(self.c,1,self.w1)
  self.assertEqual(before,self.c.total_changes)

if __name__=='__main__':unittest.main()
