"""V76: fail-closed, explainable integration data-trust assessment.

No network calls or database writes. Status is informational, not proof of
record-level completeness or financial accuracy.
"""
import time

def assess(health, now=None):
    if not isinstance(health, dict):
        raise ValueError("health must be a dict")
    now = int(time.time() if now is None else now)
    if not isinstance(now, int) or isinstance(now, bool) or now < 0:
        raise ValueError("invalid now")
    reasons = []
    if not health.get("connected"):
        return {"status": "disconnected", "safe_for_automation": False,
                "reasons": ["No connected HubSpot account"]}
    if health.get("token_status") != "valid":
        reasons.append("Connection token is not confirmed valid")
    cadence = health.get("cadence")
    if cadence not in ("hourly", "daily"):
        reasons.append("Automatic sync is not enabled")
    last_state = health.get("last_state")
    if last_state != "success":
        reasons.append("Most recent sync did not succeed")
    last_run = health.get("last_run")
    if not isinstance(last_run, int) or isinstance(last_run, bool) or last_run <= 0 or last_run > now:
        reasons.append("Last sync timestamp is missing or invalid")
    elif cadence in ("hourly", "daily"):
        limit = 7200 if cadence == "hourly" else 172800
        if now - last_run > limit:
            reasons.append("Last sync is older than the allowed freshness window")
    if reasons:
        return {"status": "untrusted", "safe_for_automation": False, "reasons": reasons}
    return {"status": "recent_sync_observed", "safe_for_automation": False,
            "reasons": ["Recent successful sync observed, but completeness and source accuracy are unverified"]}
