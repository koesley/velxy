import sqlite3
import unittest
from unittest.mock import patch
import sync_recovery_v74 as recovery
import sync_retries_v73 as retry
import business_os_v59 as crm

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.access=patch.object(crm.core,"access",return_value="owner")
        self.access.start()
        retry.setup(self.c)
    def tearDown(self):
        self.access.stop();self.c.close()
    def row(self,rid,wid="a",attempts=0,updated=100):
        self.c.execute("INSERT INTO v73_sync_retries VALUES(?,?,?,?,?,?,?,?)",
            (rid,wid,1,attempts,100,"running",100,updated))
    def test_recover_only_expired_lease(self):
        self.row("old",updated=100)
        self.row("fresh",updated=1950)
        self.assertEqual(recovery.recover(self.c,now=2000),1)
        self.assertEqual(recovery.recover(self.c,now=2000),0)
        self.assertEqual(self.c.execute("SELECT state,attempts,next_due FROM v73_sync_retries WHERE id='old'").fetchone(),("pending",1,3800))
        self.assertEqual(self.c.execute("SELECT state FROM v73_sync_retries WHERE id='fresh'").fetchone()[0],"running")
    def test_exhaust_after_attempt_limit(self):
        self.row("old",attempts=2)
        self.assertEqual(recovery.recover(self.c,now=2000),1)
        self.assertEqual(self.c.execute("SELECT state,attempts FROM v73_sync_retries WHERE id='old'").fetchone(),("exhausted",3))
    def test_monitoring_is_workspace_scoped(self):
        self.row("a1","a")
        self.row("b1","b")
        self.assertEqual(recovery.monitoring(self.c,1,"a",now=2000)["stale_running"],1)
        self.assertEqual(recovery.monitoring(self.c,1,"a",now=2000)["retry_counts"]["running"],1)
        self.assertIn("Interrupted jobs",recovery.render(self.c,1,"a"))

if __name__=="__main__":unittest.main()
