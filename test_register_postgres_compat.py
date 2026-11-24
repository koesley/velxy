"""Regression tests for the POST /register 502 (Nov 24, 2026).

Root cause: email_unsubscribe.get_or_create_token used SQLite-only
`INSERT OR IGNORE`, which is a syntax error on PostgreSQL. In POST
/register the error was swallowed by `except Exception: pass`, but
Postgres had already marked the transaction aborted, so the commit
silently rolled the new user row back while the id sequence had
already advanced. The session INSERT that follows (for the
now-missing user id) then violated the sessions_user_id_fkey foreign
key and the uncaught exception killed the handler (HTTP 502 from
Render's proxy). Introduced by PR #223, which wired
get_or_create_token into the welcome sequence.

Fix 1 (email_unsubscribe.py): the portable upsert
`INSERT ... ON CONFLICT(email) DO NOTHING`, the same form the rest of
the codebase already uses.
Fix 2 (portal.py POST /register): the session INSERT now runs in the
same `with db()` block as the user INSERT, so user + session commit
atomically and a silent rollback can never again leave a session
pointing at a missing user.

Tests run on SQLite only, so the Postgres failure mode is simulated
with a fake connection that enforces Postgres semantics (see
FakePgConnection). The live-server tests pin the atomicity on the
real handler.

Run with:
  python -m unittest test_register_postgres_compat -v
"""
import http.client
import os
import tempfile
import threading
import unittest
import urllib.parse
from http.server import ThreadingHTTPServer

# The data dir must outlive the portal import: portal reads
# VELXTRIA_DATA_DIR once at module level, so a per-test temp dir would be
# deleted while later tests still use it.
_TMP = None
_ENV = None

PASSWORD = 'RegPgPass123456!'

# Module-level counter: the data dir (and its users table) is shared by every
# test in this module, so emails must be unique across tests, not just
# within one test.
_EMAIL_N = [0]


def fresh_email():
    _EMAIL_N[0] += 1
    return 'reg-pg-%d@example.com' % _EMAIL_N[0]


def setUpModule():
    global _TMP, _ENV
    from unittest.mock import patch
    _TMP = tempfile.TemporaryDirectory()
    _ENV = patch.dict(os.environ, {
        'VELXTRIA_DATA_DIR': _TMP.name,
        'VELXTRIA_DEPLOYMENT_MODE': 'local',
        'VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT': '0',
    })
    _ENV.start()
    import portal  # noqa: F401  (imported for its module-level DATA_ROOT)
    # DATA_ROOT is fixed at first import, which may have happened in an
    # earlier test module whose temp dir is already deleted; recreate it so
    # sqlite can open the DB file again.
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


def tearDownModule():
    import portal
    try:
        with portal.db() as c:
            c.execute("DELETE FROM sessions WHERE user_id IN "
                      "(SELECT id FROM users WHERE email LIKE 'reg-pg-%@example.com')")
            c.execute("DELETE FROM email_outbox WHERE recipient LIKE 'reg-pg-%@example.com'")
            c.execute("DELETE FROM users WHERE email LIKE 'reg-pg-%@example.com'")
    except Exception:
        pass
    _ENV.stop()
    _TMP.cleanup()
    # Leave DATA_ROOT in place: later modules reuse the same imported
    # portal, and a deleted data dir breaks their DB access.
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


class FakePgError(Exception):
    """Stands in for psycopg SyntaxError / ForeignKeyViolation."""


class FakeCursor:
    def __init__(self, row=None, rowcount=0):
        self._row = row
        self.rowcount = rowcount

    def fetchone(self):
        return self._row

    def fetchall(self):
        return [self._row] if self._row is not None else []


class PgStore:
    """Committed state shared by every FakePgConnection, like one database."""

    def __init__(self):
        self.users = {}            # id -> email
        self.users_by_email = {}   # email -> id
        self.unsubscribes = {}     # email -> (token, unsubscribed)
        self.outbox = {}           # dedupe_key -> args
        self.sessions = []         # (token_hash, user_id, expires, csrf)
        self.events = []
        self.next_user_id = 1


class FakePgConnection:
    """A Postgres connection with real Postgres failure semantics.

    - SQLite-only syntax (OR IGNORE / OR REPLACE) raises, like psycopg.
    - After any error the transaction is aborted: later statements fail
      and commit() silently discards the pending writes (Postgres rolls
      an aborted transaction back on COMMIT with only a warning).
    - A fresh connection sees only committed rows; a connection sees its
      own pending writes, including for foreign-key checks.
    """

    def __init__(self, store):
        self.store = store
        self.statements = []
        self.aborted = False
        self.pending_users = {}
        self.pending_unsub = {}
        self.pending_outbox = {}
        self.pending_sessions = []
        self.pending_events = []

    def __enter__(self):
        return self

    def __exit__(self, kind, value, tb):
        try:
            if kind:
                self.rollback()
            else:
                self.commit()
        finally:
            pass
        return False

    def commit(self):
        if self.aborted:
            # Postgres: COMMIT of an aborted transaction rolls back
            # silently — no Python exception, the writes are just gone.
            self._discard()
            return
        self.store.users.update(self.pending_users)
        for uid, email in self.pending_users.items():
            self.store.users_by_email[email] = uid
        self.store.unsubscribes.update(self.pending_unsub)
        self.store.outbox.update(self.pending_outbox)
        self.store.sessions.extend(self.pending_sessions)
        self.store.events.extend(self.pending_events)
        self._discard()

    def rollback(self):
        self._discard()

    def _discard(self):
        self.pending_users = {}
        self.pending_unsub = {}
        self.pending_outbox = {}
        self.pending_sessions = []
        self.pending_events = []
        self.aborted = False

    def execute(self, sql, args=()):
        self.statements.append(sql)
        if 'OR IGNORE' in sql or 'OR REPLACE' in sql:
            self.aborted = True
            raise FakePgError(
                'SQLite-only syntax is a syntax error on Postgres: %s'
                % sql[:60])
        if self.aborted:
            raise FakePgError('current transaction is aborted')
        if sql.startswith('CREATE TABLE'):
            return FakeCursor()
        if (sql.startswith('SAVEPOINT')
                or sql.startswith('RELEASE SAVEPOINT')
                or sql.startswith('ROLLBACK TO SAVEPOINT')):
            return FakeCursor()
        if sql.startswith('INSERT INTO users('):
            uid = self.store.next_user_id
            self.store.next_user_id += 1
            self.pending_users[uid] = args[0]
            return FakeCursor(rowcount=1)
        if sql.startswith('SELECT id FROM users WHERE email=?'):
            email = args[0]
            for uid, em in self.pending_users.items():
                if em == email:
                    return FakeCursor((uid,))
            uid = self.store.users_by_email.get(email)
            return FakeCursor((uid,) if uid is not None else None)
        if sql.startswith('SELECT token FROM email_unsubscribes'):
            row = self.pending_unsub.get(args[0]) \
                or self.store.unsubscribes.get(args[0])
            return FakeCursor((row[0],) if row else None)
        if sql.startswith('SELECT unsubscribed FROM email_unsubscribes'):
            row = self.pending_unsub.get(args[0]) \
                or self.store.unsubscribes.get(args[0])
            return FakeCursor((row[1],) if row else None)
        if sql.startswith('INSERT INTO email_unsubscribes'):
            email, token = args[0], args[1]
            if email not in self.pending_unsub \
                    and email not in self.store.unsubscribes:
                self.pending_unsub[email] = (token, 0)
            return FakeCursor(rowcount=1)
        if sql.startswith('INSERT INTO email_outbox'):
            dedupe = args[6]
            if dedupe in self.pending_outbox \
                    or dedupe in self.store.outbox:
                return FakeCursor(rowcount=0)
            self.pending_outbox[dedupe] = args
            return FakeCursor(rowcount=1)
        if sql.startswith('INSERT INTO site_events'):
            self.pending_events.append(args)
            return FakeCursor(rowcount=1)
        if sql.startswith('INSERT INTO sessions VALUES'):
            token_hash, uid = args[0], args[1]
            known = set(self.store.users) | set(self.pending_users)
            if uid not in known:
                self.aborted = True
                raise FakePgError(
                    'insert or update on table "sessions" violates foreign '
                    'key constraint "sessions_user_id_fkey"')
            self.pending_sessions.append(args)
            return FakeCursor(rowcount=1)
        raise AssertionError('FakePgConnection cannot run: %s' % sql[:80])


class PostgresSyntaxTests(unittest.TestCase):
    """Fix 1: the unsubscribe token must use portable SQL."""

    def test_get_or_create_token_is_postgres_compatible(self):
        import email_unsubscribe
        conn = FakePgConnection(PgStore())
        token1 = email_unsubscribe.get_or_create_token(
            conn, 'User@Example.com')
        self.assertTrue(token1)
        # Same address, different case: the token is stable.
        token2 = email_unsubscribe.get_or_create_token(
            conn, 'user@example.com')
        self.assertEqual(token1, token2)
        for stmt in conn.statements:
            self.assertNotIn('OR IGNORE', stmt)
            self.assertNotIn('OR REPLACE', stmt)


class RegisterTransactionTests(unittest.TestCase):
    """The register chain must survive Postgres transaction semantics.

    Replicates the exact SQL order of POST /register: user INSERT,
    welcome sequence (which creates the unsubscribe token), commit,
    then the session INSERT on a fresh connection — with the real
    followups.queue_welcome driving the token creation.
    """

    def test_register_flow_survives_postgres_transaction(self):
        import followups
        store = PgStore()
        conn = FakePgConnection(store)
        uid = None
        with conn:
            conn.execute(
                'INSERT INTO users(email,salt,pw_hash,role,access,created)'
                ' VALUES (?,?,?,?,?,?)',
                ('reg-pg-flow@example.com', 'salt', 'hash',
                 'customer', 'demo', 123))
            uid = conn.execute(
                'SELECT id FROM users WHERE email=?',
                ('reg-pg-flow@example.com',)).fetchone()[0]
            try:
                followups.queue_welcome(
                    conn, uid, 'reg-pg-flow@example.com',
                    'https://example.com', seeded=False)
            except Exception:
                pass  # mirrors the swallow in portal.py POST /register
        # The session INSERT runs on a fresh connection, as in the
        # pre-fix handler: it must find the committed user row.
        conn2 = FakePgConnection(store)
        with conn2:
            conn2.execute(
                'INSERT INTO sessions VALUES (?,?,?,?)',
                ('tokhash', uid, 999, 'csrf'))
        self.assertIn(uid, store.users)
        self.assertEqual(len(store.sessions), 1)


class RegisterAtomicityTests(unittest.TestCase):
    """Fix 2: user + session commit atomically through the real handler."""

    def setUp(self):
        import portal
        self.portal = portal
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), portal.Handler)
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.port = self.server.server_address[1]

    def request(self, method, path, body=b'', content_type=None,
                headers=None):
        conn = http.client.HTTPConnection(
            '127.0.0.1', self.port, timeout=30)
        try:
            all_headers = dict(headers or {})
            if content_type:
                all_headers['Content-Type'] = content_type
            conn.request(method, path, body=body, headers=all_headers)
            resp = conn.getresponse()
            return (resp.status, dict(resp.headers), resp.read())
        finally:
            conn.close()

    def post_form(self, path, fields, headers=None):
        body = urllib.parse.urlencode(fields).encode()
        return self.request('POST', path, body=body,
                            content_type='application/x-www-form-urlencoded',
                            headers=headers)

    def test_register_creates_user_and_session_together(self):
        email = fresh_email()
        status, headers, _ = self.post_form(
            '/register', {'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        self.assertIn('velxtria_session=', headers.get('Set-Cookie', ''))
        with self.portal.db() as c:
            user = c.execute(
                'SELECT id FROM users WHERE email=?', (email,)).fetchone()
            self.assertIsNotNone(user, 'no user row created')
            rows = c.execute(
                'SELECT user_id FROM sessions WHERE user_id=?',
                (user[0],)).fetchall()
            self.assertEqual(len(rows), 1,
                             'expected exactly one session for the new user')

    def test_duplicate_register_409s_without_extra_session(self):
        email = fresh_email()
        status, _, _ = self.post_form(
            '/register', {'email': email, 'password': PASSWORD})
        self.assertEqual(status, 303)
        with self.portal.db() as c:
            uid = c.execute(
                'SELECT id FROM users WHERE email=?', (email,)).fetchone()[0]
            before = c.execute(
                'SELECT count(*) FROM sessions WHERE user_id=?',
                (uid,)).fetchone()[0]
        status, _, body = self.post_form(
            '/register', {'email': email, 'password': PASSWORD})
        self.assertEqual(status, 409)
        self.assertIn('already exists', body.decode('utf-8', 'replace'))
        with self.portal.db() as c:
            after = c.execute(
                'SELECT count(*) FROM sessions WHERE user_id=?',
                (uid,)).fetchone()[0]
        self.assertEqual(after, before,
                         'duplicate registration created a stray session')


if __name__ == '__main__':
    unittest.main()
