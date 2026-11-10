"""VELXTRIA V11 local SQLite backup, verification, and recovery status.

Run `python recovery_v11.py backup` in the project directory. This module
never restores or overwrites the live database automatically.
"""
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parent
DATA = Path(os.getenv('VELXTRIA_DATA_DIR', str(ROOT))).resolve()
DB = DATA / 'portal.sqlite3'
BACKUPS = DATA / 'velxtria_backups'

def local_only():
    if os.getenv('VELXTRIA_DATABASE_URL'):
        raise RuntimeError('Local SQLite backup is unavailable for PostgreSQL. Use your database provider backup tools.')

def digest(blob):
    return hashlib.sha256(blob).hexdigest()

def check_database(path=DB):
    local_only()
    if not Path(path).is_file():
        return {'ok': False, 'detail': 'Database file not found'}
    try:
        con = sqlite3.connect(f'file:{Path(path).resolve().as_posix()}?mode=ro', uri=True, timeout=15)
        try:
            result = con.execute('PRAGMA integrity_check').fetchone()[0]
            count = con.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        finally:
            con.close()
        return {'ok': result == 'ok', 'detail': result, 'tables': count}
    except (sqlite3.Error, OSError) as exc:
        return {'ok': False, 'detail': type(exc).__name__}

def create_backup():
    local_only()
    if not DB.is_file():
        raise RuntimeError('No existing database found. Nothing to back up.')
    BACKUPS.mkdir(parents=True, exist_ok=True)
    # SQLite's backup API safely snapshots even when the portal has open connections.
    fd, temporary = tempfile.mkstemp(prefix='.vx11-', suffix='.sqlite3', dir=BACKUPS)
    os.close(fd)
    temp_path = Path(temporary)
    try:
        source = sqlite3.connect(f'file:{DB.as_posix()}?mode=ro', uri=True, timeout=20)
        target = sqlite3.connect(temp_path)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        status = check_database(temp_path)
        if not status['ok']:
            raise RuntimeError('Snapshot integrity check failed')
        raw = temp_path.read_bytes()
        timestamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
        name = f'velxtria-{timestamp}-{digest(raw)[:10]}.zip'
        final = BACKUPS / name
        if final.exists():
            return final
        manifest = {'format': 'velxtria-sqlite-backup-v1', 'created_utc': timestamp,
                    'database': 'portal.sqlite3', 'sha256': digest(raw),
                    'bytes': len(raw), 'integrity': status['detail']}
        pending = BACKUPS / ('.' + name + '.tmp')
        try:
            with zipfile.ZipFile(pending, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr('portal.sqlite3', raw)
                z.writestr('manifest.json', json.dumps(manifest, indent=2))
            verify_backup(pending)
            os.replace(pending, final)
        finally:
            pending.unlink(missing_ok=True)
        return final
    finally:
        temp_path.unlink(missing_ok=True)

def verify_backup(path):
    local_only()
    path = Path(path)
    with zipfile.ZipFile(path) as z:
        if set(z.namelist()) != {'portal.sqlite3', 'manifest.json'}:
            raise ValueError('Unexpected backup contents')
        manifest = json.loads(z.read('manifest.json'))
        raw = z.read('portal.sqlite3')
    if manifest.get('format') != 'velxtria-sqlite-backup-v1' or digest(raw) != manifest.get('sha256'):
        raise ValueError('Backup checksum mismatch')
    if len(raw) != manifest.get('bytes'):
        raise ValueError('Backup size mismatch')
    return manifest

def render():
    if os.getenv('VELXTRIA_DATABASE_URL'):
        status = '<p>PostgreSQL is configured. Use provider-managed database backups and test restores separately. This local SQLite utility is disabled.</p>'
    else:
        health = check_database()
        backups = sorted(BACKUPS.glob('velxtria-*.zip'), reverse=True) if BACKUPS.exists() else []
        listing = ''.join('<li><code>'+escape(x.name)+'</code> · '+str(round(x.stat().st_size/1024))+' KB</li>' for x in backups[:8]) or '<li>No backups created yet</li>'
        status = ('<p><strong>Database integrity:</strong> '+('PASS' if health['ok'] else 'NEEDS ATTENTION')+'</p>'
                  '<p><strong>Detail:</strong> '+escape(health['detail'])+'</p>'
                  '<p><strong>Data folder:</strong> <code>'+escape(str(DATA))+'</code></p>'
                  '<h3>Recent local backups</h3><ul>'+listing+'</ul>'
                  '<p>To create a verified snapshot, open PowerShell in the VELXTRIA project and run:</p>'
                  '<pre>python recovery_v11.py backup</pre>'
                  '<p>To verify a backup, run: <code>python recovery_v11.py verify "FULL_PATH_TO_BACKUP.zip"</code></p>')
    return ('<section class="panel"><h1>✦ V11 / TITAN RECOVERY CENTER</h1>'
            '<p>Inspect your database and create checksum-verified, consistent local snapshots. No database resets or automatic restores.</p>'
            +status+'<p><strong>Important:</strong> Backups in the same folder or computer do not protect against drive failure. Copy verified ZIP files to a separate secure location. The tool backs up SQLite data only; separately preserve report files, secrets, and external services.</p></section>')

if __name__ == '__main__':
    try:
        if len(sys.argv) == 2 and sys.argv[1] == 'backup':
            print('Backup created:', create_backup())
        elif len(sys.argv) == 3 and sys.argv[1] == 'verify':
            print(json.dumps(verify_backup(sys.argv[2]), indent=2))
        elif len(sys.argv) == 2 and sys.argv[1] == 'check':
            result = check_database()
            print(json.dumps(result, indent=2))
            sys.exit(0 if result['ok'] else 1)
        else:
            print('Usage: python recovery_v11.py backup | check | verify BACKUP.zip')
            sys.exit(2)
    except (RuntimeError, ValueError, OSError, sqlite3.Error, zipfile.BadZipFile) as error:
        print('Recovery error:', error, file=sys.stderr)
        sys.exit(1)
