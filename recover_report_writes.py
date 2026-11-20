"""Conservative, opt-in recovery for interrupted VELXTRIA report writes.

Default mode lists stale pending writes without changing data. --apply
rechecks each entry and deletes only objects whose report metadata does
not exist, then marks the journal entry cleaned. Never touches a ready
report. Intended for a controlled maintenance window.
"""
import argparse
import sys
import time


def reconcile(connection_factory, remove, *, apply=False, min_age_seconds=86400, current_time=None):
    cutoff = int(time.time() if current_time is None else current_time) - min_age_seconds
    with connection_factory() as c:
        candidates = c.execute(
            "SELECT report_id,user_id FROM report_write_journal "
            "WHERE state='pending' AND created<? ORDER BY created LIMIT 100",
            (cutoff,)
        ).fetchall()
    results = {'stale': len(candidates), 'cleaned': 0, 'protected': 0, 'failed': 0}
    for report_id, user_id in candidates:
        with connection_factory() as c:
            report = c.execute(
                'SELECT id FROM reports WHERE id=? AND user_id=?',
                (report_id, user_id)
            ).fetchone()
            pending = c.execute(
                "SELECT state,created FROM report_write_journal WHERE report_id=? AND user_id=?",
                (report_id, user_id)
            ).fetchone()
        if report or not pending or pending[0] != 'pending' or pending[1] >= cutoff:
            results['protected'] += 1
            continue
        if not apply:
            continue
        try:
            # Recheck metadata immediately before removal. Only operate
            # during a maintenance window with no concurrent report writers.
            with connection_factory() as c:
                if c.execute('SELECT id FROM reports WHERE id=?', (report_id,)).fetchone():
                    results['protected'] += 1
                    continue
            remove(user_id, report_id)
            with connection_factory() as c:
                c.execute(
                    "UPDATE report_write_journal SET state='cleaned' "
                    "WHERE report_id=? AND user_id=? AND state='pending'",
                    (report_id, user_id)
                )
            results['cleaned'] += 1
        except Exception:
            results['failed'] += 1
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description='Audit or reconcile stale report-write journal entries')
    parser.add_argument('--apply', action='store_true', help='Delete orphan objects; run only with report writers stopped')
    parser.add_argument('--min-age-hours', type=int, default=24)
    args = parser.parse_args(argv)
    if args.min_age_hours < 24:
        parser.error('Minimum age must be at least 24 hours')
    import portal
    import persistent
    result = reconcile(portal.db, persistent.remove, apply=args.apply,
                       min_age_seconds=args.min_age_hours * 3600)
    print('Report write recovery:', result)
    return 1 if result['failed'] else 0


if __name__ == '__main__':
    sys.exit(main())
