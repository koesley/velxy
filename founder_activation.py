"""Founder-only, read-only V61 report-activation cohorts from first-party records.

A ready saved report is a verifiable product milestone, NOT proof of business
value, retention, billing, or customer success. No customer identifiers leave
the query and no analytics events or user records are written.
"""
import html
import time

SECONDS_PER_DAY = 86400


def report_activation(conn, as_of=None):
    cutoff = int(time.time() if as_of is None else as_of)
    if cutoff < 0:
        raise ValueError("Invalid observation time")
    # One row per user, with the earliest ready report after account creation.
    # Filtering the report join avoids counting pre-signup or failed reports.
    rows = conn.execute(
        "SELECT u.created, MIN(r.created) FROM users u "
        "LEFT JOIN reports r ON r.user_id=u.id AND r.status='ready' "
        "AND r.created>=u.created AND r.created<=? "
        "WHERE u.created<=? AND u.role='customer' "
        "GROUP BY u.id,u.created",
        (cutoff, cutoff),
    ).fetchall()
    mature = 0
    converted = 0
    all_saved = 0
    for created, first_report in rows:
        created = int(created)
        if first_report is not None:
            all_saved += 1
        if created + 7 * SECONDS_PER_DAY <= cutoff:
            mature += 1
            if first_report is not None and int(first_report) < created + 7 * SECONDS_PER_DAY:
                converted += 1
    return {
        "signup_accounts": len(rows),
        "accounts_with_saved_report": all_saved,
        "mature_seven_day_cohort": mature,
        "saved_report_within_seven_days": converted,
        "seven_day_rate_pct": round(100 * converted / mature, 2) if mature else None,
    }


def panel_html(metrics):
    rate = metrics["seven_day_rate_pct"]
    fields = (
        ("Customer accounts observed", metrics["signup_accounts"]),
        ("Accounts with at least one ready saved report", metrics["accounts_with_saved_report"]),
        ("Signups with seven full days of observation", metrics["mature_seven_day_cohort"]),
        ("Mature signups saving a ready report within seven days", metrics["saved_report_within_seven_days"]),
        ("Seven-day saved-report activation", "Not available (no mature cohort)" if rate is None else str(rate) + "%"),
    )
    rows = "".join("<tr><th scope='row'>" + html.escape(label) +
                   "</th><td>" + html.escape(str(value)) + "</td></tr>"
                   for label, value in fields)
    return ("<section class='panel'><h2>V61 — Verified saved-report activation</h2>"
            "<p>Based on existing customer account creation and ready saved-report "
            "timestamps. Only signups at least seven days old enter the seven-day "
            "denominator. This is an observed product milestone, not proof of "
            "customer business value, payment, or retention. Anonymous demo "
            "runs and unsaved results are excluded.</p>"
            "<table><tbody>" + rows + "</tbody></table>"
            "<p>Older records and late report imports may affect counts. "
            "No individual customer information is shown.</p></section>")
