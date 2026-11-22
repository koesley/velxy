"""Regression tests for stale execution state transitions."""
import sqlite3
import unittest
from unittest.mock import patch
import sovereign_execution_v56 as execution

class ExecutionTransitionIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        execution.setup(self.c)
        self.c.execute("INSERT INTO sv56_exec_jobs(id,workspace_id,strategy_id,scenario_code,action_type,idempotency_key,status,created_by,created,updated,expires) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                       ("job1","workspace1","strategy1","scenario","create_review_task","unique-key","proposed",1,1,1,4102444800))
        self.c.execute("""CREATE TRIGGER prevent_job_transition BEFORE UPDATE ON sv56_exec_jobs
                          BEGIN SELECT RAISE(IGNORE); END""")
        self.access = patch.object(execution.core, "access", return_value=None)
        self.access.start()
    def tearDown(self):
        self.access.stop()
        self.c.close()
    def test_ignored_transition_does_not_emit_false_audit(self):
        with self.assertRaisesRegex(ValueError, "concurrently"):
            execution.change(self.c,1,"workspace1","job1","reject")
        self.assertEqual(self.c.execute("SELECT status FROM sv56_exec_jobs").fetchone()[0],"proposed")
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM sv56_exec_events").fetchone()[0],0)
    def test_successful_transition_emits_single_audit(self):
        self.c.execute("DROP TRIGGER prevent_job_transition")
        execution.change(self.c,1,"workspace1","job1","reject")
        self.assertEqual(self.c.execute("SELECT status FROM sv56_exec_jobs").fetchone()[0],"rejected")
        self.assertEqual(self.c.execute("SELECT event FROM sv56_exec_events").fetchall(),[("reject",)])
    def test_second_transition_is_rejected_without_extra_event(self):
        self.c.execute("DROP TRIGGER prevent_job_transition")
        execution.change(self.c,1,"workspace1","job1","reject")
        with self.assertRaisesRegex(ValueError, "Invalid execution state transition"):
            execution.change(self.c,1,"workspace1","job1","reject")
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM sv56_exec_events").fetchone()[0],1)

if __name__=="__main__":
    unittest.main()
