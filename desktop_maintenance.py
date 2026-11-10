"""Offline diagnostics and consistent SQLite backup for VELXTRIA Desktop."""
import argparse
import datetime
import json
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path


def data_root():
    return Path(os.getenv('VELXTRIA_DATA_DIR') or Path(os.getenv('LOCALAPPDATA') or Path.home()) / 'VELXTRIA' / 'Data')


def diagnose(root=None):
    root = Path(root or data_root())
    db = root / 'portal.sqlite3'
    report = {
        'data_dir': str(root),
        'data_dir_exists': root.is_dir(),
        'database_exists': db.is_file(),
        'database_bytes': db.stat().st_size if db.is_file() else 0,
        'database_integrity': None,
        'backup_count': len(list((root / 'Backups').glob('*.sqlite3'))) if (root / 'Backups').is_dir() else 0,
    }
    if db.is_file():
        try:
            with closing(sqlite3.connect(f'file:{db.as_posix()}?mode=ro', uri=True, timeout=5)) as conn:
                report['database_integrity'] = conn.execute('PRAGMA quick_check').fetchone()[0]
        except sqlite3.Error as exc:
            report['database_integrity'] = 'error: ' + str(exc)
    return report


def backup(root=None, keep=10):
    root = Path(root or data_root())
    db = root / 'portal.sqlite3'
    if not db.is_file():
        raise FileNotFoundError('No database to back up: ' + str(db))
    dest = root / 'Backups'
    dest.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = dest / ('VELXTRIA_' + timestamp + '.sqlite3')
    try:
        with closing(sqlite3.connect(f'file:{db.as_posix()}?mode=ro', uri=True, timeout=15)) as source:
            with closing(sqlite3.connect(output)) as target:
                source.backup(target)
        with closing(sqlite3.connect(output)) as check:
            if check.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup integrity check failed')
    except Exception:
        output.unlink(missing_ok=True)
        raise
    backups = sorted(dest.glob('VELXTRIA_*.sqlite3'), reverse=True)
    for old in backups[max(1, keep):]:
        old.unlink()
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['diagnose', 'backup'])
    parser.add_argument('--data-dir')
    parser.add_argument('--keep', type=int, default=10)
    args = parser.parse_args()
    try:
        if args.action == 'diagnose':
            print(json.dumps(diagnose(args.data_dir), indent=2))
        else:
            print('Backup verified:', backup(args.data_dir, args.keep))
    except Exception as exc:
        print('VELXTRIA maintenance failed:', exc, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
