"""Conservative, opt-in recovery for interrupted VELXTRIA report writes.

Default mode lists stale pending writes without changing data. --apply
rechecks each entry and deletes only objects whose report metadata does
not exist, then marks the journal entry cleaned. Never touches a ready
report. Intended for a controlled maintenance window.
"""
import argparse
import os
import sys
import time


def reconcile(connection_factory, remove, *, apply=False, min_age_seconds=86400, current_time=None, verify_absent=None):
    if apply and not callable(verify_absent):
        raise ValueError('Destructive recovery requires an object-absence verifier')
    cutoff = int(time.time() if current_time is None else current_time) - min_age_seconds
    with connection_factory() as c:
        candidates = c.execute(
            "SELECT report_id,user_id FROM report_write_journal "
            "WHERE state='pending' AND created<? ORDER BY created LIMIT 100",
            (cutoff,)
        ).fetchall()
    with connection_factory() as c:
        stranded = c.execute(
            "SELECT COUNT(*) FROM report_write_journal "
            "WHERE state='recovering' AND created<?", (cutoff,)
        ).fetchone()[0]
    results = {'stale': len(candidates), 'recovering_needs_review': stranded,
               'cleaned': 0, 'protected': 0, 'failed': 0}
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
            # Claim the stale entry atomically. A concurrent writer must
            # not be able to commit its report while cleanup is underway.
            with connection_factory() as c:
                claim = c.execute(
                    "UPDATE report_write_journal SET state='recovering' "
                    "WHERE report_id=? AND user_id=? AND state='pending' AND created<? "
                    "AND NOT EXISTS (SELECT 1 FROM reports WHERE id=?)",
                    (report_id, user_id, cutoff, report_id)
                )
                claimed = claim.rowcount == 1
            if not claimed:
                results['protected'] += 1
                continue
            try:
                remove(user_id, report_id)
                # A successful delete API response alone is not proof the
                # object disappeared. Production passes an authenticated
                # read-back verifier that only accepts explicit HTTP 404.
                if verify_absent is not None:
                    verify_absent(user_id, report_id)
            except Exception:
                with connection_factory() as c:
                    c.execute(
                        "UPDATE report_write_journal SET state='pending' "
                        "WHERE report_id=? AND user_id=? AND state='recovering'",
                        (report_id, user_id)
                    )
                raise
            with connection_factory() as c:
                c.execute(
                    "UPDATE report_write_journal SET state='cleaned' "
                    "WHERE report_id=? AND user_id=? AND state='recovering'",
                    (report_id, user_id)
                )
            results['cleaned'] += 1
        except Exception:
            results['failed'] += 1
    return results


def verify_storage_absent(retrieve, missing_error, user_id, report_id):
    """Fail closed unless authenticated storage explicitly reports not found."""
    try:
        retrieve(user_id, report_id, None)
    except missing_error:
        return
    raise RuntimeError('Storage object absence was not verified')


def inspect_stranded(connection_factory, retrieve, *, min_age_seconds=86400, current_time=None):
    """Read-only audit of interrupted recovery, with no customer data in output.

    A 404-like exception is not trusted as proof of absence here: storage
    failures and authorization errors can be indistinguishable in adapters.
    Only a successful read is classified as object_present; all failures
    require manual investigation before any destructive action.
    """
    cutoff = int(time.time() if current_time is None else current_time) - min_age_seconds
    result = {'stranded': 0, 'report_present': 0, 'object_present': 0,
              'storage_unverified': 0}
    with connection_factory() as c:
        rows = c.execute(
            "SELECT report_id,user_id FROM report_write_journal "
            "WHERE state='recovering' AND created<? ORDER BY created LIMIT 100",
            (cutoff,)
        ).fetchall()
    result['stranded'] = len(rows)
    for report_id, user_id in rows:
        with connection_factory() as c:
            exists = c.execute(
                'SELECT id FROM reports WHERE id=?', (report_id,)
            ).fetchone()
        if exists:
            result['report_present'] += 1
            continue
        try:
            retrieve(user_id, report_id, None)
            result['object_present'] += 1
        except Exception:
            result['storage_unverified'] += 1
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='Audit or reconcile stale report-write journal entries')
    parser.add_argument('--apply', action='store_true', help='Delete orphan objects; run only with report writers stopped')
    parser.add_argument('--inspect-stranded', action='store_true', help='Read-only inspect stranded recovery objects')
    parser.add_argument('--min-age-hours', type=int, default=24)
    args = parser.parse_args(argv)
    if args.min_age_hours < 24:
        parser.error('Minimum age must be at least 24 hours')
    if args.apply and os.getenv('VELXTRIA_REPORT_RECOVERY_MAINTENANCE') != 'I_HAVE_STOPPED_REPORT_WRITERS':
        parser.error('--apply requires VELXTRIA_REPORT_RECOVERY_MAINTENANCE=I_HAVE_STOPPED_REPORT_WRITERS after stopping report writers')
    import portal
    import persistent
    if args.inspect_stranded:
        summary = inspect_stranded(portal.db, persistent.retrieve,
                                   min_age_seconds=args.min_age_hours * 3600)
        print('Stranded recovery audit:', summary)
        if summary['stranded']:
            return 1
    if args.apply and not persistent.REMOTE:
        parser.error('--apply requires configured remote storage; local deletion is unsupported')
    result = reconcile(
        portal.db, persistent.remove, apply=args.apply,
        min_age_seconds=args.min_age_hours * 3600,
        verify_absent=(lambda owner, identifier: verify_storage_absent(
            persistent.retrieve, persistent.StorageObjectNotFound, owner, identifier
        )) if args.apply else None
    )
    print('Report write recovery:', result)
    return 1 if result['failed'] or result['recovering_needs_review'] else 0


if __name__ == '__main__':
    sys.exit(main())
