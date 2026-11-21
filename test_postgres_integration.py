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

    def test_invoice_legacy_integer_columns_migrate_to_bigint(self):
        """Upgrade legacy PG invoice columns without losing existing records."""
        import persistent
        import business_v4
        from unittest.mock import patch
        with patch.object(persistent, 'DATABASE_URL', TEST_URL):
            with persistent.PgConnection() as adapter:
                # PostgreSQL forbids permanent invoice FKs to temporary users.
                # This disposable CI database uses a permanent parent fixture.
                adapter.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY)")
                adapter.execute("INSERT INTO users(id) VALUES (?)", (1,))
                adapter.execute(
                    "CREATE TEMP TABLE vx4_invoices "
                    "(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,contact_id TEXT,"
                    "description TEXT NOT NULL,amount_cents INTEGER NOT NULL,"
                    "status TEXT NOT NULL DEFAULT 'draft',due_at INTEGER NOT NULL,"
                    "created_at INTEGER NOT NULL,paid_at INTEGER NOT NULL DEFAULT 0)"
                )
                adapter.execute(
                    "INSERT INTO vx4_invoices(id,user_id,description,amount_cents,due_at,created_at) "
                    "VALUES (?,?,?,?,?,?)",
                    ('legacy',1,'Existing',12500,2000000000,2000000000)
                )
                business_v4.setup(adapter)
                adapter.execute(
                    "INSERT INTO vx4_invoices(id,user_id,description,amount_cents,due_at,created_at) "
                    "VALUES (?,?,?,?,?,?)",
                    ('future',1,'Large invoice',10000000000,4102444800,4102444800)
                )
                self.assertEqual(adapter.execute(
                    "SELECT amount_cents,due_at FROM vx4_invoices WHERE id='future'"
                ).fetchone(), (10000000000,4102444800))
                self.assertEqual(adapter.execute(
                    "SELECT amount_cents FROM vx4_invoices WHERE id='legacy'"
                ).fetchone(), (12500,))

    def test_postgres_daily_buckets_do_not_round_up(self):
        """A PostgreSQL numeric cast used to shift afternoons into tomorrow."""
        import persistent
        import site_stats
        from unittest.mock import patch
        midnight = 2000000000 - (2000000000 % 86400)
        with patch.object(persistent, 'DATABASE_URL', TEST_URL):
            with persistent.PgConnection() as adapter:
                adapter.execute(
                    "CREATE TEMP TABLE site_events "
                    "(created INTEGER NOT NULL, event TEXT NOT NULL, detail TEXT NOT NULL)"
                )
                for seconds in (1, 43201, 86399):
                    adapter.execute(
                        "INSERT INTO site_events(created,event,detail) VALUES (?,?,?)",
                        (midnight + seconds, 'landing_view', 'boundary')
                    )
                _, daily, _ = site_stats.summary(adapter, days=36500)
                self.assertEqual(daily, [(midnight, {'landing_view': 3})])

    def test_analytics_error_does_not_abort_business_transaction(self):
        """PostgreSQL must allow the business write after telemetry fails."""
        import persistent
        import site_stats
        from unittest.mock import patch
        with patch.object(persistent, 'DATABASE_URL', TEST_URL):
            with persistent.PgConnection() as adapter:
                adapter.execute(
                    "CREATE TEMP TABLE site_events "
                    "(created INTEGER NOT NULL, event TEXT NOT NULL "
                    "CHECK (event='never'), detail TEXT NOT NULL)"
                )
                adapter.execute("CREATE TEMP TABLE vx_business_probe (id INTEGER PRIMARY KEY)")
                adapter.execute("INSERT INTO vx_business_probe VALUES (?)", (1,))
                site_stats.record(adapter, 'landing_view')
                adapter.execute("INSERT INTO vx_business_probe VALUES (?)", (2,))
                self.assertEqual(adapter.execute(
                    "SELECT count(*) FROM vx_business_probe"
                ).fetchone(), (2,))

    def test_real_adapter_iteration_and_rowcount(self):
        """Exercise the actual PgConnection wrapper, not only psycopg."""
        import persistent
        from unittest.mock import patch
        with patch.object(persistent, 'DATABASE_URL', TEST_URL):
            with persistent.PgConnection() as adapter:
                adapter.execute("CREATE TEMP TABLE vx_adapter_probe (id INTEGER PRIMARY KEY)")
                self.assertEqual(adapter.execute(
                    "INSERT INTO vx_adapter_probe (id) VALUES (?)", (10,)
                ).rowcount, 1)
                self.assertEqual(list(adapter.execute(
                    "SELECT id FROM vx_adapter_probe WHERE id=?", (10,)
                )), [(10,)])
                self.assertEqual(adapter.execute(
                    "UPDATE vx_adapter_probe SET id=? WHERE id=?", (11, 10)
                ).rowcount, 1)

    def test_analytics_summary_on_postgres(self):
        """Validate the production analytics query and iteration path."""
        import persistent
        import site_stats
        from unittest.mock import patch
        with patch.object(persistent, 'DATABASE_URL', TEST_URL):
            with persistent.PgConnection() as adapter:
                # A temporary table shadows the real analytics table so this
                # integration test cannot change any persistent analytics.
                adapter.execute(
                    "CREATE TEMP TABLE site_events "
                    "(created INTEGER NOT NULL, event TEXT NOT NULL, detail TEXT NOT NULL)"
                )
                adapter.execute(
                    "INSERT INTO site_events(created,event,detail) VALUES (?,?,?)",
                    (2000000000, 'landing_view', 'ci')
                )
                totals, daily, recent = site_stats.summary(adapter, days=36500)
                self.assertEqual(totals['landing_view'], 1)
                self.assertEqual(recent[0][1], 'landing_view')
                self.assertTrue(daily)
                self.assertEqual(daily[0][1]['landing_view'], 1)
                adapter.execute(
                    "INSERT INTO site_events(created,event,detail) VALUES (?,?,?)",
                    (2000000050, 'landing_view', '<img src=x onerror=alert(1)>')
                )
                totals, daily, recent = site_stats.summary(adapter, days=36500)
                self.assertEqual(totals['landing_view'], 2)
                self.assertEqual(len(daily), 1)
                self.assertEqual(daily[0][1]['landing_view'], 2)
                page = site_stats.stats_html(totals, daily, recent)
                self.assertNotIn('<img src=x', page)
                self.assertIn('&lt;img', page)

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

    def test_schema_lock_serializes_concurrent_instances(self):
        """A second process cannot enter schema setup until first commits."""
        import psycopg
        first = psycopg.connect(TEST_URL)
        second = psycopg.connect(TEST_URL)
        try:
            first.execute("SELECT pg_advisory_xact_lock(871329014, 20261120)")
            second.execute("SET lock_timeout = '250ms'")
            with self.assertRaises(psycopg.errors.LockNotAvailable):
                second.execute("SELECT pg_advisory_xact_lock(871329014, 20261120)")
            second.rollback()
            first.commit()
            second.execute("SELECT pg_advisory_xact_lock(871329014, 20261120)")
            second.commit()
        finally:
            first.close()
            second.close()

    def test_quoted_question_marks_survive_execution(self):
        from sql_params import translate_qmark
        result = self.conn.execute(translate_qmark(
            "SELECT '?'::text, ?::text"
        ), ("value",)).fetchone()
        self.assertEqual(result, ("?", "value"))


if __name__ == "__main__":
    unittest.main()
