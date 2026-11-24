"""Live usage scoreboard for the landing page: real social proof.

The numbers come only from the append-only site_events log — never
hardcoded, never fabricated, never rounded up:

- demos: demo_run events (every instant demo, anonymous or signed-in).
- reports: demo_run + report_generated events. A demo result page and a
  saved report are distinct artifacts the engine produced; a demo that
  is later claimed as a report therefore counts once under each.
- rows checked / rows flagged: the accepted/rejected counts carried in
  those events' detail strings (``accepted=N rejected=M``). The same
  claim caveat applies to rows as to reports.
- revenue: the ``paid=<cents>`` token in the same detail strings,
  recorded by the demo and report handlers going forward. Demos run
  before that token existed contribute no revenue — the metric starts
  at 0 and is omitted until real demos record it, rather than being
  backfilled from any decaying source. (demo_shares rows expire after
  30 days, so they can never be an all-time source.)

Rules: a metric of 0 is omitted; if the database read fails, the whole
section is hidden (get_stats returns None). Counts are cached in
memory for 5 minutes so the landing page — the most-hit page — does
not query on every view.
"""

import re
import time

import site_stats

CACHE_TTL_SECONDS = 300

_ACCEPTED_RE = re.compile(r'accepted=(\d+)')
_REJECTED_RE = re.compile(r'rejected=(\d+)')
_PAID_RE = re.compile(r'paid=(\d+)')

_CACHE = {'at': 0, 'stats': None}


def paid_cents_from_stats(stats):
    """Paid revenue in cents from an engine report's stats lines.

    The engine reports ``Paid revenue (accepted Paid orders only):
    $800.00``; the same line-scan demo_shares.scorecard uses. Missing
    or malformed lines mean no paid revenue, never a guess.
    """
    for line in stats or []:
        if line.startswith('Paid revenue'):
            raw = line.split(':', 1)[-1].strip().replace('$', '').replace(',', '')
            try:
                return int(round(float(raw) * 100))
            except ValueError:
                return 0
    return 0


def compute_stats(conn):
    """Aggregate the event log into scoreboard numbers, or None when
    the database read fails. One cheap read over the append-only log.
    """
    try:
        site_stats.ensure(conn)
        rows = conn.execute(
            "SELECT event, detail FROM site_events "
            "WHERE event IN ('demo_run','report_generated')").fetchall()
    except Exception:
        return None
    demos = reports = rows_checked = rows_flagged = revenue_cents = 0
    for event, detail in rows:
        detail = detail or ''
        accepted = _ACCEPTED_RE.search(detail)
        rejected = _REJECTED_RE.search(detail)
        paid = _PAID_RE.search(detail)
        a = int(accepted.group(1)) if accepted else 0
        r = int(rejected.group(1)) if rejected else 0
        if event == 'demo_run':
            demos += 1
        reports += 1
        rows_checked += a + r
        rows_flagged += r
        if paid:
            revenue_cents += int(paid.group(1))
    return {'demos': demos, 'reports': reports, 'rows_checked': rows_checked,
            'rows_flagged': rows_flagged, 'revenue_cents': revenue_cents}


def get_stats(conn):
    """Cached scoreboard numbers; None when the read fails, so the
    caller hides the section. A failed read is never cached — the next
    request retries.
    """
    now = time.time()
    if _CACHE['stats'] is not None and now - _CACHE['at'] < CACHE_TTL_SECONDS:
        return _CACHE['stats']
    stats = compute_stats(conn)
    if stats is not None:
        _CACHE['at'] = now
        _CACHE['stats'] = stats
    return stats


def reset_cache():
    """Forget the cached numbers (tests; a fresh deploy starts empty)."""
    _CACHE['at'] = 0
    _CACHE['stats'] = None


def _fmt(n):
    return '{:,}'.format(n)


def scoreboard_items(stats):
    """(value, label) pairs for the nonzero metrics only, in display
    order. Revenue is floored to whole dollars — never rounded up.
    """
    items = []
    if stats['demos']:
        items.append((_fmt(stats['demos']),
                      'demo' + ('s' if stats['demos'] != 1 else '') + ' run'))
    if stats['reports']:
        items.append((_fmt(stats['reports']),
                      'report' + ('s' if stats['reports'] != 1 else '') + ' generated'))
    if stats['rows_checked']:
        items.append((_fmt(stats['rows_checked']), 'rows checked'))
    if stats['rows_flagged']:
        items.append((_fmt(stats['rows_flagged']), 'problem rows flagged'))
    dollars = stats['revenue_cents'] // 100
    if dollars:
        items.append(('$' + _fmt(dollars), 'in sales checked'))
    return items
