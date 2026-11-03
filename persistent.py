
"""VELXY V4: fail-closed PostgreSQL and private Supabase report storage."""

import os
import sqlite3
import json
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

DATABASE_URL = os.getenv('VELXTRIA_DATABASE_URL', '')
REQUIRE = os.getenv('VELXTRIA_REQUIRE_PERSISTENCE', '0') == '1'

URL = os.getenv('VELXTRIA_SUPABASE_URL', '').rstrip('/')
KEY = os.getenv('VELXTRIA_SUPABASE_SERVICE_KEY', '')
BUCKET = os.getenv('VELXTRIA_SUPABASE_BUCKET', 'velxy-reports')

REMOTE = bool(DATABASE_URL)

if REQUIRE and not (REMOTE and URL and KEY):
    raise RuntimeError(
        'Persistent mode requires VELXTRIA_DATABASE_URL, '
        'VELXTRIA_SUPABASE_URL and VELXTRIA_SUPABASE_SERVICE_KEY'
    )

if REMOTE and not (URL and KEY):
    raise RuntimeError(
        'PostgreSQL requires private Supabase storage credentials '
        '(no local ZIP fallback)'
    )


class PgConnection:
    def __init__(self):
        import psycopg
        self.conn = psycopg.connect(
            DATABASE_URL,
            connect_timeout=10
        )
        self.cursor = None

    def execute(self, sql, args=()):
        # The existing application uses SQLite question-mark placeholders.
        sql = sql.replace('?', '%s')
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


def connect(local_db):
    if REMOTE:
        return PgConnection()

    if REQUIRE:
        raise RuntimeError('Persistent storage is required')

    c = sqlite3.connect(local_db, timeout=15)
    c.execute('PRAGMA foreign_keys=ON')
    return c


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
        (target / (str(report_id) + '.zip')).write_bytes(payload)


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
    if REMOTE:
        path = '%s/%s/%s.zip' % (
            BUCKET,
            user_id,
            report_id
        )
        try:
            _request('DELETE', path)
        except RuntimeError:
            pass
