
"""VELXY V4: fail-closed PostgreSQL and private Supabase report storage."""

import os
import sqlite3
import json
import urllib.request
import urllib.parse
import urllib.error
from sql_params import translate_qmark
from pathlib import Path

DATABASE_URL = os.getenv('VELXTRIA_DATABASE_URL', '')
REQUIRE = os.getenv('VELXTRIA_REQUIRE_PERSISTENCE', '0') == '1'

URL = os.getenv('VELXTRIA_SUPABASE_URL', '').rstrip('/')
KEY = os.getenv('VELXTRIA_SUPABASE_SERVICE_KEY', '')
BUCKET = os.getenv('VELXTRIA_SUPABASE_BUCKET', 'velxy-reports')

REMOTE = bool(DATABASE_URL)

# PostgreSQL and private report-object storage are independent services.
# Report operations remain fail-closed when Supabase is not configured.
if REQUIRE and not REMOTE:
    raise RuntimeError('Persistent mode requires VELXTRIA_DATABASE_URL')


class PgConnection:
    def __init__(self):
        import psycopg
        self.conn = psycopg.connect(
            DATABASE_URL,
            connect_timeout=10
        )
        self.cursor = None

    def execute(self, sql, args=()):
        # Translate placeholders only outside SQL strings and comments.
        sql = translate_qmark(sql)
        self.cursor = self.conn.execute(sql, args)
        return self

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, kind, value, tb):
        try:
            if kind:
                self.conn.rollback()
            else:
                self.conn.commit()
        finally:
            self.conn.close()


class ManagedSQLiteConnection(sqlite3.Connection):
    """Commit/rollback and close when used in a with block.

    sqlite3.Connection's default context manager does not close the connection.
    """
    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()


def connect(local_db):
    if REMOTE:
        return PgConnection()

    if REQUIRE:
        raise RuntimeError('Persistent storage is required')

    c = sqlite3.connect(local_db, timeout=15, factory=ManagedSQLiteConnection)
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=15000')
    return c


class StorageObjectNotFound(FileNotFoundError):
    """The storage provider explicitly returned HTTP 404 for an object."""


def _request(method, path, payload=None):
    if not (URL and KEY):
        raise RuntimeError('Supabase Storage is not configured')

    # Encode each storage path segment safely.
    encoded_path = '/'.join(
        urllib.parse.quote(str(x), safe='')
        for x in path.split('/')
    )

    endpoint = URL + '/storage/v1/object/' + encoded_path

    headers = {
        'apikey': KEY,
        'Authorization': 'Bearer ' + KEY
    }

    if payload is not None:
        headers['Content-Type'] = 'application/zip'
        headers['x-upsert'] = 'false'

    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers=headers,
        method=method
    )

    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            return response.read()

    except urllib.error.HTTPError as e:
        if e.code == 404 and method == 'GET':
            raise StorageObjectNotFound('Private report object not found') from None
        # Show the actual Supabase error, without exposing
        # credentials, authorization headers, or the request URL.
        details = e.read().decode(
            'utf-8',
            errors='replace'
        )

        # Avoid exposing arbitrary server responses.
        try:
            parsed = json.loads(details)
            if isinstance(parsed, dict):
                safe_details = {
                    k: parsed[k]
                    for k in ('statusCode', 'error', 'message', 'code')
                    if k in parsed and isinstance(
                        parsed[k], (str, int, float)
                    )
                }
                details = json.dumps(safe_details)
            else:
                details = 'Unexpected storage error response'
        except (ValueError, TypeError):
            details = 'Non-JSON storage error response'

        raise RuntimeError(
            'Private storage request failed '
            '(HTTP %s): %s' % (e.code, details[:500])
        ) from None

    except urllib.error.URLError:
        raise RuntimeError(
            'Private storage is unreachable'
        ) from None


def store(user_id, report_id, payload, local_reports):
    if REMOTE:
        path = '%s/%s/%s.zip' % (
            BUCKET,
            user_id,
            report_id
        )
        _request('POST', path, payload)

    else:
        target = Path(local_reports) / str(user_id)
        target.mkdir(
            parents=True,
            exist_ok=True
        )
        # Atomic local replacement: a crash during writing must not expose a
        # truncated ZIP as a completed report.
        import tempfile
        import os as _os
        destination = target / (str(report_id) + '.zip')
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target, prefix='.report-', suffix='.tmp', delete=False) as out:
                temporary = Path(out.name)
                out.write(payload)
                out.flush()
                _os.fsync(out.fileno())
            _os.replace(temporary, destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def retrieve(user_id, report_id, local_reports):
    if REMOTE:
        path = '%s/%s/%s.zip' % (
            BUCKET,
            user_id,
            report_id
        )
        # Supabase authenticated object download endpoint.
        return _request('GET', 'authenticated/' + path)

    return (
        Path(local_reports)
        / str(user_id)
        / (str(report_id) + '.zip')
    ).read_bytes()


def remove(user_id, report_id):
    """Remove one report object using Supabase Storage's remove API.

    A failed remote deletion raises an error rather than silently claiming
    success. Callers may choose whether cleanup is best-effort.
    """
    if REMOTE:
        if not (URL and KEY):
            raise RuntimeError('Supabase Storage is not configured')
        object_name = '%s/%s.zip' % (user_id, report_id)
        endpoint = URL + '/storage/v1/object/remove/' + urllib.parse.quote(BUCKET, safe='')
        request = urllib.request.Request(
            endpoint,
            data=json.dumps({'prefixes': [object_name]}).encode('utf-8'),
            headers={
                'apikey': KEY,
                'Authorization': 'Bearer ' + KEY,
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                result = json.loads(response.read(65536))
            if not isinstance(result, list):
                raise RuntimeError('Storage deletion returned an unexpected response')
        except (urllib.error.URLError, ValueError, TypeError) as exc:
            raise RuntimeError('Private storage deletion failed') from None
    # Local report files remain managed by the caller's local report root.
