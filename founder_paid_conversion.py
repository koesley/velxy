"""Founder-only read-only V60/V61 observed paid-conversion cohorts.

Only BTCPay mainnet orders marked settled by the invoice-verification path
count. These are recorded settlements, not refund-adjusted revenue or profit.
"""
import html
import time

DAY = 86400


def paid_cohorts(conn, as_of=None):
    now = int(time.time()) if as_of is None else int(as_of)
    if now < 0:
        raise ValueError("Invalid observation time")
    try:
        rows = conn.execute(
            "SELECT u.id,u.created,"
            "(SELECT MIN(r.created) FROM reports r WHERE r.user_id=u.id "
            "AND r.status='ready' AND r.created>=u.created AND r.created<=?),"
            "(SELECT MIN(o.settled_at) FROM btcpay_orders o "
            "WHERE o.user_id=u.id AND o.network='mainnet' AND o.status='settled' "
            "AND o.invoice_id IS NOT NULL AND o.invoice_id<>'' "
            "AND o.settled_at>=u.created AND o.settled_at<=?) "
            "FROM users u WHERE u.role='customer' AND u.created<=?",
            (now, now, now)).fetchall()
    except Exception as exc:
        # Fresh local installations may not have initialized BTCPay tables.
        # Never conceal other SQL or database errors.
        msg = str(exc).lower()
        if "no such table: btcpay_orders" in msg or (
                "relation" in msg and "btcpay_orders" in msg and "does not exist" in msg):
            return {"available": False}
        raise
    mature = activated = paid = activated_paid = 0
    weekly = {}
    activation_delays = []
    settlement_delays = []
    first_day_activated = first_week_settled = 0
    for _, created, first_ready, first_paid in rows:
        try:
            created = int(created)
            first_ready = None if first_ready is None else int(first_ready)
            first_paid = None if first_paid is None else int(first_paid)
        except (TypeError, ValueError, OverflowError):
            continue
        if created < 0 or created + 30 * DAY > now:
            continue
        mature += 1
        has_first_value = first_ready is not None and created <= first_ready < created + 7 * DAY
        has_payment = first_paid is not None and created <= first_paid < created + 30 * DAY
        if has_first_value:
            delay = first_ready - created
            activation_delays.append(delay)
            first_day_activated += int(delay < DAY)
        if has_payment:
            delay = first_paid - created
            settlement_delays.append(delay)
            first_week_settled += int(delay < 7 * DAY)
        activated += int(has_first_value)
        paid += int(has_payment)
        activated_paid += int(has_first_value and has_payment)
        week = created // (7 * DAY) * (7 * DAY)
        counts = weekly.setdefault(week, [0, 0, 0, 0])
        counts[0] += 1
        counts[1] += int(has_first_value)
        counts[2] += int(has_payment)
        counts[3] += int(has_first_value and has_payment)
    def median_days(delays):
        if not delays:
            return None
        ordered = sorted(delays)
        n = len(ordered)
        if n % 2:
            seconds = ordered[n // 2]
        else:
            seconds = (ordered[n // 2 - 1] + ordered[n // 2]) / 2
        return round(seconds / DAY, 2)

    nonactivated = mature - activated
    nonactivated_paid = paid - activated_paid
    return {
        "first_day_activated": first_day_activated,
        "first_week_settled": first_week_settled,
        "median_days_to_first_value": median_days(activation_delays),
        "median_days_to_settlement": median_days(settlement_delays),
        "nonactivated_signups": nonactivated,
        "nonactivated_settled": nonactivated_paid,
        "nonactivated_paid_conversion_pct": (
            round(100 * nonactivated_paid / nonactivated, 2) if nonactivated else None),
        "available": True, "mature_30d_signups": mature,
        "first_week_activated": activated, "settled_within_30d": paid,
        "activated_and_settled": activated_paid,
        "paid_conversion_pct": round(100 * paid / mature, 2) if mature else None,
        "activated_paid_conversion_pct": round(100 * activated_paid / activated, 2) if activated else None,
        "weekly": tuple((w, *counts) for w, counts in sorted(weekly.items(), reverse=True)[:8]),
    }


def panel_html(metrics):
    if not metrics["available"]:
        return ("<section class='panel'><h2>V60/V61 — Observed paid conversion</h2>"
                "<p>Unavailable: mainnet order records have not been initialized. "
                "No paid-conversion rate is inferred.</p></section>")
    trend_rows = "".join(
        "<tr><td>" + html.escape(time.strftime("%Y-%m-%d", time.gmtime(week))) +
        "</td>" + "".join("<td>" + str(count) + "</td>" for count in counts) + "</tr>"
        for week, *counts in metrics.get("weekly", ()))
    trend = ("<h3>Recent mature signup weeks</h3>"
             "<p>Each row is a signup week with a fully observed 30-day window; "
             "the most recent eight eligible weeks are shown. Counts are customers, "
             "not invoices or revenue. Activation and settlement may occur in either order; "
             "this comparison does not establish causation.</p>"
             "<table><thead><tr><th>Signup week (UTC)</th><th>Signups</th>"
             "<th>Activated</th><th>Settled</th><th>Both</th></tr></thead><tbody>" +
             (trend_rows or "<tr><td colspan='5'>No mature signup weeks</td></tr>") +
             "</tbody></table>")
    fields = (
        ("Signups with 30 full days observed", metrics["mature_30d_signups"]),
        ("Saved a ready report within seven days", metrics["first_week_activated"]),
        ("Saved a ready report within 24 hours", metrics["first_day_activated"]),
        ("Median days to first ready report (first-week activators)", metrics["median_days_to_first_value"]),
        ("Settled mainnet invoice within seven days", metrics["first_week_settled"]),
        ("Median days to settlement (30-day converters)", metrics["median_days_to_settlement"]),
        ("Recorded settled mainnet invoice within 30 days", metrics["settled_within_30d"]),
        ("Both first-week saved report and 30-day settlement", metrics["activated_and_settled"]),
        ("30-day observed settled conversion", metrics["paid_conversion_pct"]),
        ("30-day settled conversion among first-week activated", metrics["activated_paid_conversion_pct"]),
        ("Signups without first-week ready report", metrics["nonactivated_signups"]),
        ("Settled without first-week ready report", metrics["nonactivated_settled"]),
        ("30-day settled conversion without first-week activation", metrics["nonactivated_paid_conversion_pct"]),
    )
    rows = "".join("<tr><th scope='row'>" + html.escape(label) + "</th><td>" +
                   ("Not available" if value is None else html.escape(str(value)) +
                    ("%" if label.startswith("30-day") else "")) + "</td></tr>"
                   for label, value in fields)
    return ("<section class='panel'><h2>V60/V61 — Observed paid conversion</h2>"
            "<p>Only customer signups with 30 complete days are included. Settlements are "
            "recorded BTCPay mainnet invoices verified by the payment workflow, not checkout "
            "starts, pending invoices, hypothetical scenarios, or proof of net revenue. "
            "Refunds and chargebacks are not deducted; these are historical recorded "
            "settlements, not active paid retention or recurring revenue. "
            "Time-to-value and time-to-settlement medians use only observed qualifying events; "
            "missing events do not become zero-day conversions. "
            "No individual customer identifiers are displayed.</p>"
            "<table><tbody>" + rows + "</tbody></table>" + trend + "</section>")
