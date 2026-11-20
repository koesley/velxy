"""PostgreSQL integration tests against an isolated CI database.

Requires VELXTRIA_TEST_DATABASE_URL, never the production connection variable.
Only temporary tables are created and dropped automatically on connection close.
"""
import os
import unittest

TEST_URL = os.environ.get("VELXTRIA_TEST_DATABASE_URL", "")


@unittest.skipUnless(TEST_URL, "Set VELXTRIA_TEST_DATABASE_URL for isolated integration testing")
class PostgreSQLIntegrationTests(unittest.TestCase):
    def setUp(self):
        import psycopg
        self.conn = psycopg.connect(TEST_URL)
        self.conn.execute("BEGIN")
        self.conn.execute(
            "CREATE TEMP TABLE velxtria_integration_probe "
            "(id BIGINT PRIMARY KEY, label TEXT NOT NULL) ON COMMIT PRESERVE ROWS"
        )

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def test_insert_read_update_and_delete(self):
        from sql_params import translate_qmark
        self.conn.execute(translate_qmark(
            "INSERT INTO velxtria_integration_probe (id,label) VALUES (?,?)"
        ), (1, "first"))
        self.assertEqual(self.conn.execute(translate_qmark(
            "SELECT label FROM velxtria_integration_probe WHERE id=?"
        ), (1,)).fetchone(), ("first",))
        updated = self.conn.execute(translate_qmark(
            "UPDATE velxtria_integration_probe SET label=? WHERE id=?"
        ), ("updated", 1))
        self.assertEqual(updated.rowcount, 1)
        self.assertEqual(self.conn.execute(
            "SELECT label FROM velxtria_integration_probe WHERE id=1"
        ).fetchone(), ("updated",))
        deleted = self.conn.execute(translate_qmark(
            "DELETE FROM velxtria_integration_probe WHERE id=?"
        ), (1,))
        self.assertEqual(deleted.rowcount, 1)

    def test_transaction_rollback(self):
        self.conn.execute("SAVEPOINT before_write")
        self.conn.execute("INSERT INTO velxtria_integration_probe VALUES (2,'rollback')")
        self.conn.execute("ROLLBACK TO SAVEPOINT before_write")
        self.assertEqual(self.conn.execute(
            "SELECT count(*) FROM velxtria_integration_probe WHERE id=2"
        ).fetchone(), (0,))

    def test_quoted_question_marks_survive_execution(self):
        from sql_params import translate_qmark
        result = self.conn.execute(translate_qmark(
            "SELECT '?'::text, ?::text"
        ), ("value",)).fetchone()
        self.assertEqual(result, ("?", "value"))


if __name__ == "__main__":
    unittest.main()
