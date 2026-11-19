"""Descriptive lead-source and activity attribution, not causal ROI or verified revenue."""
import html
import urllib.parse
from collections import defaultdict
from decimal import Decimal
import business_os_v59 as bos
import customer_outcomes_v33 as outcomes
import revenue_execution_v29 as execution


def analyze(c, uid, wid):
    bos.core.access(c, uid, wid)
    bos.init(c)
    outcomes.setup(c)
    execution.setup(c)
    leads = c.execute("SELECT id,source,status FROM bos59_leads WHERE workspace_id=?", (wid,)).fetchall()
    source_by_lead = {}
    stats = defaultdict(lambda: {
        "leads": 0, "won_leads": 0, "lost_leads": 0,
        "reported_payments": 0, "reported_cents": 0,
        "outcomes": 0, "tasks": 0, "completed_tasks": 0,
        "payment_leads": 0, "invalid_payment_records": 0,
    })
    for lid, source, status in leads:
        name = source.strip() if source and source.strip() else "Unspecified"
        source_by_lead[lid] = name
        bucket = stats[name]
        bucket["leads"] += 1
        if status == "won":
            bucket["won_leads"] += 1
        elif status == "lost":
            bucket["lost_leads"] += 1

    payment_leads = defaultdict(set)
    for lid, kind, amount in c.execute(
        "SELECT lead_id,kind,amount_cents FROM vx_outcomes33 WHERE workspace_id=?", (wid,)
    ):
        if lid not in source_by_lead:
            continue
        name = source_by_lead[lid]
        bucket = stats[name]
        bucket["outcomes"] += 1
        if kind == "payment_reported":
            # Never add malformed, negative, or non-integer claims to displayed money.
            if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
                bucket["invalid_payment_records"] += 1
                continue
            bucket["reported_payments"] += 1
            bucket["reported_cents"] += amount
            payment_leads[name].add(lid)

    for lid, status in c.execute(
        "SELECT lead_id,status FROM vx_revenue_tasks29 WHERE workspace_id=?", (wid,)
    ):
        if lid not in source_by_lead:
            continue
        bucket = stats[source_by_lead[lid]]
        bucket["tasks"] += 1
        if status == "done":
            bucket["completed_tasks"] += 1

    rows = []
    for source, metrics in stats.items():
        closed = metrics["won_leads"] + metrics["lost_leads"]
        rows.append({
            "source": source, **metrics,
            "payment_leads": len(payment_leads[source]),
            "closed_leads": closed,
            "won_share_pct": round(metrics["won_leads"] / metrics["leads"] * 100, 1)
                if metrics["leads"] else None,
            "closed_win_pct": round(metrics["won_leads"] / closed * 100, 1)
                if closed else None,
            "task_completion_pct": round(metrics["completed_tasks"] / metrics["tasks"] * 100, 1)
                if metrics["tasks"] else None,
        })
    return sorted(rows, key=lambda r: (-r["reported_cents"], -r["won_leads"], r["source"]))


def _money(cents):
    value = Decimal(cents) / Decimal(100)
    return "$" + format(value, ",.2f")


def render(c, uid, wid):
    rows = analyze(c, uid, wid)
    e = lambda v: html.escape(str(v), quote=True)
    w = urllib.parse.quote(wid, safe="")
    out = ['<section class="panel"><h1>Lead Source & Outcome Intelligence</h1>',
           '<p>Compare sources using recorded leads, manually marked sales stages, '
           'self-reported payment claims and internal tasks. Sources are manually entered labels. '
           'These are descriptive associations, not causal attribution, verified receipts, '
           'profit, or return on investment. A won stage does not prove payment.</p>',
           '<p><a href="/customer-outcomes?w=' + w + '">Customer outcomes</a> · '
           '<a href="/revenue-execution?w=' + w + '">Execution tasks</a></p></section>']
    if not rows:
        return ''.join(out) + '<section class="panel"><p>No leads recorded in this workspace yet.</p></section>'
    for row in rows:
        closed_rate = (str(row["closed_win_pct"]) + "%"
                       if row["closed_win_pct"] is not None else "N/A (no closed leads)")
        completion = (str(row["task_completion_pct"]) + "%"
                      if row["task_completion_pct"] is not None else "N/A (no tasks)")
        out.append('<section class="panel"><h2>' + e(row["source"]) + '</h2>'
                   '<p>Leads: ' + str(row["leads"]) +
                   ' · Won-marked: ' + str(row["won_leads"]) +
                   ' · Lost-marked: ' + str(row["lost_leads"]) +
                   ' · Open or other: ' + str(row["leads"] - row["closed_leads"]) + '</p>'
                   '<p>Won share of all leads: ' + str(row["won_share_pct"]) +
                   '% · Win rate among closed leads: ' + closed_rate + '</p>'
                   '<p>Self-reported payment records: ' + str(row["reported_payments"]) +
                   ' · Distinct leads reporting payments: ' + str(row["payment_leads"]) +
                   ' · Reported amount: ' + _money(row["reported_cents"]) + '</p>'
                   '<p>Recorded outcomes: ' + str(row["outcomes"]) +
                   ' · Tasks completed: ' + str(row["completed_tasks"]) +
                   ' / ' + str(row["tasks"]) + ' (' + completion + ')</p>')
        if row["invalid_payment_records"]:
            out.append('<p>Excluded invalid or negative payment claims: ' +
                       str(row["invalid_payment_records"]) + '.</p>')
        out.append('</section>')
    return ''.join(out)
