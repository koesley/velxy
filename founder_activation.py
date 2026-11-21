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
    weekly = {}
    mature = 0
    converted = 0
    all_saved = 0
    first_day = 0
    late_saved = 0
    never_saved = 0
    invalid_timestamps = 0
    middle_saved = 0
    for created, first_report in rows:
        try:
            created = int(created)
            first_report = None if first_report is None else int(first_report)
        except (TypeError, ValueError, OverflowError):
            invalid_timestamps += 1
            continue
        if created < 0 or (first_report is not None and first_report < created):
            invalid_timestamps += 1
            continue
        if first_report is not None:
            all_saved += 1
        if created + 7 * SECONDS_PER_DAY <= cutoff:
            mature += 1
            if first_report is None:
                never_saved += 1
            elif int(first_report) < created + SECONDS_PER_DAY:
                first_day += 1
            elif first_report >= created + 7 * SECONDS_PER_DAY:
                late_saved += 1
            else:
                middle_saved += 1
            if first_report is not None and int(first_report) < created + 7 * SECONDS_PER_DAY:
                converted += 1
            week = (created // (7 * SECONDS_PER_DAY)) * (7 * SECONDS_PER_DAY)
            bucket = weekly.setdefault(week, [0, 0])
            bucket[0] += 1
            bucket[1] += int(first_report is not None and int(first_report) < created + 7 * SECONDS_PER_DAY)
    return {
        "signup_accounts": len(rows) - invalid_timestamps,
        "excluded_invalid_timestamp_accounts": invalid_timestamps,
        "accounts_with_saved_report": all_saved,
        "mature_seven_day_cohort": mature,
        "saved_report_within_seven_days": converted,
        "saved_report_within_one_day": first_day,
        "saved_report_days_one_to_seven": middle_saved,
        "one_day_rate_pct": round(100 * first_day / mature, 2) if mature else None,
        "seven_day_lift_pct_points": round(100 * middle_saved / mature, 2) if mature else None,
        "saved_report_after_seven_days": late_saved,
        "mature_accounts_without_saved_report": never_saved,
        "seven_day_rate_pct": round(100 * converted / mature, 2) if mature else None,
        "weekly_cohorts": tuple((week, counts[0], counts[1]) for week, counts in sorted(weekly.items(), reverse=True)[:8]),
    }


def panel_html(metrics):
    rate = metrics["seven_day_rate_pct"]
    fields = (
        ("Customer accounts observed", metrics["signup_accounts"]),
        ("Accounts with at least one ready saved report", metrics["accounts_with_saved_report"]),
        ("Signups with seven full days of observation", metrics["mature_seven_day_cohort"]),
        ("Mature signups saving a ready report within seven days", metrics["saved_report_within_seven_days"]),
        ("Mature signups saving within 24 hours", metrics["saved_report_within_one_day"]),
        ("Mature signups first saving between 24 hours and seven days", metrics["saved_report_days_one_to_seven"]),
        ("24-hour saved-report activation", "Not available (no mature cohort)" if metrics["one_day_rate_pct"] is None else str(metrics["one_day_rate_pct"]) + "%"),
        ("Additional activation between 24 hours and seven days", "Not available (no mature cohort)" if metrics["seven_day_lift_pct_points"] is None else str(metrics["seven_day_lift_pct_points"]) + " percentage points"),
        ("Excluded accounts with invalid timestamps", metrics["excluded_invalid_timestamp_accounts"]),
        ("Mature signups first saving after seven days", metrics["saved_report_after_seven_days"]),
        ("Mature signups with no ready saved report observed", metrics["mature_accounts_without_saved_report"]),
        ("Seven-day saved-report activation", "Not available (no mature cohort)" if rate is None else str(rate) + "%"),
    )
    rows = "".join("<tr><th scope='row'>" + html.escape(label) +
                   "</th><td>" + html.escape(str(value)) + "</td></tr>"
                   for label, value in fields)
    from datetime import datetime, timezone
    cohorts = metrics.get("weekly_cohorts", ())
    cohort_rows = "".join("<tr><th scope='row'>" + datetime.fromtimestamp(week, timezone.utc).strftime("%Y-%m-%d") + "</th><td>" + str(total) + "</td><td>" + str(activated) + "</td><td>" + str(total - activated) + "</td><td>" + str(round(100 * activated / total, 2)) + "%</td></tr>" for week, total, activated in cohorts)
    cohort_html = ("<h3>Recent mature signup weeks (UTC)</h3><p>Only accounts with seven full days of observation are included. Not activated does not mean churned or lost.</p><table><thead><tr><th>Week starting</th><th>Mature signups</th><th>Activated</th><th>Not activated</th><th>Rate</th></tr></thead><tbody>" + cohort_rows + "</tbody></table>") if cohorts else "<p>No mature signup weeks available.</p>"
    return ("<section class='panel'><h2>V61 — Verified saved-report activation</h2>"
            "<p>Based on existing customer account creation and ready saved-report "
            "timestamps. Only signups at least seven days old enter the seven-day "
            "denominator. This is an observed product milestone, not proof of "
            "customer business value, payment, or retention. Anonymous demo "
            "runs and unsaved results are excluded.</p>"
            "<p>Diagnostic: compare 24-hour activation with seven-day activation to identify early onboarding friction. The 24-hour-to-seven-day lift isolates customers who reached the milestone later in the first week. Late saves show delayed adoption, while no saved report is an observed missing milestone, not proof of churn. These are descriptive counts, not causal conclusions.</p>"
            "<table><tbody>" + rows + "</tbody></table>" + cohort_html
            + "<p>Older records, malformed timestamps, and late report imports may affect counts. Invalid signup timestamps are excluded rather than treated as customer activity. "
            "No individual customer information is shown.</p></section>")
