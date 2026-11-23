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
        "SELECT u.created, MIN(r.created), "
        "CASE WHEN EXISTS (SELECT 1 FROM reports repeat_r WHERE repeat_r.user_id=u.id "
        "AND repeat_r.status='ready' AND repeat_r.created>=u.created+? "
        "AND repeat_r.created<u.created+? AND repeat_r.created<=?) THEN 1 ELSE 0 END "
        "FROM users u "
        "LEFT JOIN reports r ON r.user_id=u.id AND r.status='ready' "
        "AND r.created>=u.created AND r.created<=? "
        "WHERE u.created<=? AND u.role='customer' "
        "GROUP BY u.id,u.created",
        (7 * SECONDS_PER_DAY, 30 * SECONDS_PER_DAY, cutoff, cutoff, cutoff),
    ).fetchall()
    weekly = {}
    weekly_day_one = {}
    mature_day_one = 0
    day_one_saved = 0
    weekly_stages = {}
    mature = 0
    converted = 0
    all_saved = 0
    first_day = 0
    late_saved = 0
    never_saved = 0
    invalid_timestamps = 0
    middle_saved = 0
    thirty_day_eligible = 0
    thirty_day_repeat = 0
    # Separate mature first-day and delayed-first-week cohorts for actionable
    # onboarding diagnostics; these are associations, not causal effects.
    repeat_by_activation_speed = {"within_24h": [0, 0], "24h_to_7d": [0, 0]}
    weekly_repeat = {}  # Signup-week buckets; only fully observed 30-day cohorts.
    for created, first_report, has_repeat in rows:
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
        # A 24-hour conversion denominator should not wait for seven days.
        # Keep the legacy seven-day-mature diagnostic intact for compatibility.
        if created + SECONDS_PER_DAY <= cutoff:
            mature_day_one += 1
            activated_day_one = int(first_report is not None and first_report < created + SECONDS_PER_DAY)
            day_one_saved += activated_day_one
            day_one_week = (created // (7 * SECONDS_PER_DAY)) * (7 * SECONDS_PER_DAY)
            day_one_bucket = weekly_day_one.setdefault(day_one_week, [0, 0])
            day_one_bucket[0] += 1
            day_one_bucket[1] += activated_day_one
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
                if created + 30 * SECONDS_PER_DAY <= cutoff:
                    thirty_day_eligible += 1
                    thirty_day_repeat += int(has_repeat == 1)
                    week_30 = (created // (7 * SECONDS_PER_DAY)) * (7 * SECONDS_PER_DAY)
                    week_counts = weekly_repeat.setdefault(week_30, [0, 0])
                    week_counts[0] += 1
                    week_counts[1] += int(has_repeat == 1)
                    speed = "within_24h" if first_report < created + SECONDS_PER_DAY else "24h_to_7d"
                    repeat_by_activation_speed[speed][0] += 1
                    repeat_by_activation_speed[speed][1] += int(has_repeat == 1)
            week = (created // (7 * SECONDS_PER_DAY)) * (7 * SECONDS_PER_DAY)
            bucket = weekly.setdefault(week, [0, 0])
            bucket[0] += 1
            bucket[1] += int(first_report is not None and int(first_report) < created + 7 * SECONDS_PER_DAY)
            stages = weekly_stages.setdefault(week, [0, 0, 0])
            stages[0] += 1
            stages[1] += int(first_report is not None and first_report < created + SECONDS_PER_DAY)
            stages[2] += int(first_report is not None and created + SECONDS_PER_DAY <= first_report < created + 7 * SECONDS_PER_DAY)
    speed_metrics = {
        key: {"eligible": counts[0], "repeat_users": counts[1],
              "rate_pct": round(100 * counts[1] / counts[0], 2) if counts[0] else None}
        for key, counts in repeat_by_activation_speed.items()
    }
    return {
        "mature_24_hour_cohort": mature_day_one,
        "saved_report_within_24h_observed": day_one_saved,
        "observed_24h_activation_rate_pct": round(100 * day_one_saved / mature_day_one, 2) if mature_day_one else None,
        "weekly_24h_activation": tuple((week, counts[0], counts[1]) for week, counts in sorted(weekly_day_one.items(), reverse=True)[:8]),
        "repeat_usage_by_first_save_speed": speed_metrics,
        "weekly_mature_repeat_usage": tuple(
            (week, counts[0], counts[1])
            for week, counts in sorted(weekly_repeat.items(), reverse=True)[:8]),
        "first_week_activated_with_30_day_observation": thirty_day_eligible,
        "first_week_activated_with_later_ready_report": thirty_day_repeat,
        "later_report_usage_rate_pct": round(100 * thirty_day_repeat / thirty_day_eligible, 2) if thirty_day_eligible else None,
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
        "weekly_activation_stages": tuple((week, *counts) for week, counts in sorted(weekly_stages.items(), reverse=True)[:8]),
    }


def panel_html(metrics):
    rate = metrics["seven_day_rate_pct"]
    fields = (
        ("Customer accounts observed", metrics["signup_accounts"]),
        ("Signups with 24 full hours of observation", metrics.get("mature_24_hour_cohort", 0)),
        ("Those signups saving a ready report within 24 hours", metrics.get("saved_report_within_24h_observed", 0)),
        ("24-hour activation among 24-hour-mature signups", "Not available (no 24-hour-mature signups)" if metrics.get("observed_24h_activation_rate_pct") is None else str(metrics["observed_24h_activation_rate_pct"]) + "%"),
        ("First-week activated accounts with 30 days observed", metrics.get("first_week_activated_with_30_day_observation", 0)),
        ("Those accounts with a further ready report on days 7–30", metrics.get("first_week_activated_with_later_ready_report", 0)),
        ("Observed later-report usage among eligible activated accounts", "Not available (no eligible 30-day cohort)" if metrics.get("later_report_usage_rate_pct") is None else str(metrics["later_report_usage_rate_pct"]) + "%"),
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
    speed = metrics.get("repeat_usage_by_first_save_speed", {})
    speed_labels = (("within_24h", "First saved within 24 hours"),
                    ("24h_to_7d", "First saved between 24 hours and seven days"))
    speed_rows = "".join(
        "<tr><th scope='row'>" + html.escape(label) + "</th><td>" +
        html.escape(str(speed.get(key, {}).get("eligible", 0))) + "</td><td>" +
        html.escape(str(speed.get(key, {}).get("repeat_users", 0))) + "</td><td>" +
        ("Not available" if speed.get(key, {}).get("rate_pct") is None else
         html.escape(str(speed[key]["rate_pct"])) + "%") + "</td></tr>"
        for key, label in speed_labels)
    speed_html = ("<h3>30-day repeat use by first-save timing</h3>"
                  "<p>Only first-week activated customers with a complete 30-day observation window are included. "
                  "Compare the two segments to prioritize onboarding research; differences do not establish causation or paid retention.</p>"
                  "<table><thead><tr><th>First ready report</th><th>Eligible</th><th>Further ready report</th><th>Observed rate</th></tr></thead><tbody>"
                  + speed_rows + "</tbody></table>")
    from datetime import datetime, timezone
    repeat_weeks = metrics.get("weekly_mature_repeat_usage", ())
    repeat_week_rows = "".join(
        "<tr><th scope='row'>" + datetime.fromtimestamp(week, timezone.utc).strftime("%Y-%m-%d") +
        "</th><td>" + str(eligible) + "</td><td>" + str(repeated) +
        "</td><td>" + str(round(100 * repeated / eligible, 2)) + "%</td></tr>"
        for week, eligible, repeated in repeat_weeks if eligible > 0)
    repeat_week_html = (
        "<h3>Repeat usage by mature signup week (UTC)</h3>"
        "<p>Only customers who first saved within seven days and have 30 full days of observation "
        "are included. Rates describe later ready-report use, not paid retention. "
        "Recent weeks may be absent until their observation window matures.</p>"
        "<table><thead><tr><th>Week starting</th><th>Eligible activated</th>"
        "<th>Used again on days 7–30</th><th>Observed rate</th></tr></thead><tbody>" +
        repeat_week_rows + "</tbody></table>"
    ) if repeat_week_rows else "<p>No mature 30-day signup weeks available.</p>"
    day_one_weeks = metrics.get("weekly_24h_activation", ())
    day_one_rows = "".join(
        "<tr><th scope='row'>" + datetime.fromtimestamp(week, timezone.utc).strftime("%Y-%m-%d") +
        "</th><td>" + str(total) + "</td><td>" + str(saved) + "</td><td>" +
        str(round(100 * saved / total, 2)) + "%</td></tr>"
        for week, total, saved in day_one_weeks if total > 0)
    day_one_html = (
        "<h3>24-hour activation by signup week (UTC)</h3>"
        "<p>Includes customers with a complete first 24 hours, even if they have not reached day seven. "
        "This is saved-report usage, not a payment or proof of customer value.</p>"
        "<table><thead><tr><th>Week starting</th><th>Mature signups</th>"
        "<th>Saved within 24h</th><th>Observed rate</th></tr></thead><tbody>" +
        day_one_rows + "</tbody></table>"
    ) if day_one_rows else "<p>No signups with a complete 24-hour observation window.</p>"
    cohorts = metrics.get("weekly_cohorts", ())
    stages = {week: (total, day_one, delayed) for week, total, day_one, delayed in metrics.get("weekly_activation_stages", ())}
    cohort_rows = "".join("<tr><th scope='row'>" + datetime.fromtimestamp(week, timezone.utc).strftime("%Y-%m-%d") + "</th><td>" + str(total) + "</td><td>" + str(stages.get(week, (total, 0, activated))[1]) + "</td><td>" + str(stages.get(week, (total, 0, activated))[2]) + "</td><td>" + str(activated) + "</td><td>" + str(total - activated) + "</td><td>" + str(round(100 * activated / total, 2)) + "%</td></tr>" for week, total, activated in cohorts)
    cohort_html = ("<h3>Recent mature signup weeks (UTC)</h3><p>Only accounts with seven full days of observation are included. 24-hour and later first-week saves are mutually exclusive; the seven-day total is their sum. Not activated does not mean churned or lost.</p><table><thead><tr><th>Week starting</th><th>Mature signups</th><th>Saved within 24h</th><th>First saved 24h–7d</th><th>Activated within 7d</th><th>Not activated within 7d</th><th>7d rate</th></tr></thead><tbody>" + cohort_rows + "</tbody></table>") if cohorts else "<p>No mature signup weeks available.</p>"
    return ("<section class='panel'><h2>V61 — Verified saved-report activation</h2>"
            "<p>Based on existing customer account creation and ready saved-report "
            "timestamps. The 24-hour metric uses signups at least 24 hours old; only signups at least seven days old enter the seven-day "
            "denominator. This is an observed product milestone, not proof of "
            "customer business value, payment, or retention. Anonymous demo "
            "runs and unsaved results are excluded.</p>"
            "<p>Repeat-usage diagnostic: among accounts that first saved within seven days and have at least 30 days of observation, count a further ready saved report from day 7 up to (but excluding) day 30. This is observed repeat product use, not proof of paid retention, recurring revenue, or customer outcomes. No eligible accounts means the rate is unavailable.</p>"
            "<p>Diagnostic: compare 24-hour activation with seven-day activation to identify early onboarding friction. The 24-hour-to-seven-day lift isolates customers who reached the milestone later in the first week. Late saves show delayed adoption, while no saved report is an observed missing milestone, not proof of churn. These are descriptive counts, not causal conclusions.</p>"
            "<table><tbody>" + rows + "</tbody></table>" + day_one_html + speed_html + repeat_week_html + cohort_html
            + "<p>Older records, malformed timestamps, and late report imports may affect counts. Invalid signup timestamps are excluded rather than treated as customer activity. "
            "No individual customer information is shown.</p></section>")
