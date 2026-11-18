"""VELXTRIA outreach deliverability guard.

Manual-only classification. Never sends messages or bypasses recipient filters.
"""
import re

def classify_bounce(body):
    text=(body or "").lower()
    if any(x in text for x in ("550 5.1.1","550 5.1.0","user does not exist","address does not exist","recipient not found","account that you tried to reach does not exist","address locked or deactivated")):
        return "suppress_permanent"
    if any(x in text for x in ("550 5.4.1","recipient address rejected","message blocked","policy that", "554.5.7.1")):
        return "suppress_rejected"
    if any(x in text for x in ("dns error","timed out","delivery incomplete","relay access denied","remote server is misconfigured")):
        return "hold_for_verification"
    return "needs_manual_review"

def summarize_bounces(messages):
    """Return statuses for full bounce bodies; duplicate notices collapse by address.

    messages: iterable of dicts with recipient and body keys. Do not pass
    marketing copy as bounce evidence. No external requests are performed.
    """
    priority={"needs_manual_review":0,"hold_for_verification":1,"suppress_rejected":2,"suppress_permanent":3}
    result={}
    for message in messages:
        email=(message.get("recipient") or "").strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",email):
            continue
        status=classify_bounce(message.get("body",""))
        previous=result.get(email)
        if previous is None or priority[status]>priority[previous]:
            result[email]=status
    return result

def eligible_for_new_outreach(address, suppression_statuses):
    """Fail closed: only explicitly cleared addresses are eligible.

    Caller must separately verify address source, relevance and consent/legal
    requirements. This function never authorizes sending by itself.
    """
    return suppression_statuses.get(address.strip().lower())=="verified_clear"
