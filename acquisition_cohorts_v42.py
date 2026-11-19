"""Period-aligned, descriptive acquisition activity; never a causal ROI estimate."""
import calendar
import datetime as dt
import html
import urllib.parse
from decimal import Decimal
import business_os_v59 as bos
import acquisition_intelligence_v35 as acquisition


def month_bounds(now=None, months=6):
    """Six complete UTC calendar months, oldest first; exclude partial current month."""
    if now is None:
        now = dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone aware")
    now = now.astimezone(dt.timezone.utc)
    anchor = now.year * 12 + now.month - 1
    result = []
    for offset in range(months, 0, -1):
        index = anchor - offset
        year, month_zero = divmod(index, 12)
        month = month_zero + 1
        start = calendar.timegm((year, month, 1, 0, 0, 0))
        end_index = index + 1
        end_year, end_month_zero = divmod(end_index, 12)
        end = calendar.timegm((end_year, end_month_zero + 1, 1, 0, 0, 0))
        result.append((f"{year:04d}-{month:02d}", start, end))
    return result


def analyze(c, uid, wid, now=None):
    """Match lead creation and expense entry months, not lifetime outcome timestamps."""
    bos.core.access(c, uid, wid)
    bos.init(c)
    acquisition.setup(c)
    periods = month_bounds(now)
    lower, upper = periods[0][1], periods[-1][2]
    leads = c.execute(
        """SELECT source,created,COUNT(*) FROM bos59_leads
           WHERE workspace_id=? AND created>=? AND created<?
           GROUP BY source,created""", (wid, lower, upper)).fetchall()
    costs = c.execute(
        """SELECT source,created,SUM(amount_cents) FROM vx_acquisition_cost35
           WHERE workspace_id=? AND created>=? AND created<?
           GROUP BY source,created""", (wid, lower, upper)).fetchall()
    buckets = {}
    for label, start, end in periods:
        buckets[label] = {"month": label, "start": start, "end": end,
                          "leads": 0, "cost_cents": 0, "sources": {}}

    def month_for(timestamp):
        try:
            moment = dt.datetime.fromtimestamp(int(timestamp), dt.timezone.utc)
        except (ValueError, TypeError, OverflowError, OSError):
            return None
        return moment.strftime("%Y-%m")

    for records, key in ((leads, "leads"), (costs, "cost_cents")):
        for source, created, amount in records:
            label = month_for(created)
            if label not in buckets:
                continue
            name = source.strip() if isinstance(source, str) and source.strip() else "Unspecified"
            bucket = buckets[label]
            bucket[key] += int(amount)
            channel = bucket["sources"].setdefault(name, {"source": name, "leads": 0, "cost_cents": 0})
            channel[key] += int(amount)
    for bucket in buckets.values():
        bucket["sources"] = sorted(bucket["sources"].values(),
                                   key=lambda x: (-x["cost_cents"], -x["leads"], x["source"]))
    return list(buckets.values())


def render(c, uid, wid, now=None):
    rows = analyze(c, uid, wid, now)
    e = lambda value: html.escape(str(value), quote=True)
    money = lambda cents: "$" + format(Decimal(cents) / 100, ",.2f")
    out = ['<section class="panel"><h2>Six completed months: acquisition activity</h2>',
           '<p>Compares leads created and manually recorded expenses entered in the same UTC month. '
           'Expenses may describe earlier campaigns; lead source labels are manually entered. '
           'This is not a cohort conversion rate, verified customer acquisition cost, ROI, '
           'or evidence that spending caused a lead. Current month is excluded.</p>']
    for bucket in rows:
        out.append('<h3>' + e(bucket["month"]) + '</h3><p>New leads: ' +
                   str(bucket["leads"]) + ' · Expenses entered: ' +
                   money(bucket["cost_cents"]) + '</p>')
        if bucket["sources"]:
            out.append('<table><thead><tr><th>Source</th><th>New leads</th>'
                       '<th>Expenses entered</th></tr></thead><tbody>')
            for channel in bucket["sources"]:
                out.append('<tr><td>' + e(channel["source"]) + '</td><td>' +
                           str(channel["leads"]) + '</td><td>' +
                           money(channel["cost_cents"]) + '</td></tr>')
            out.append('</tbody></table>')
    out.append('</section>')
    return ''.join(out)
