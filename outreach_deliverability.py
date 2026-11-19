"""VELXTRIA outreach deliverability guard.

Manual-only classification. Never sends messages or bypasses recipient filters.
"""
import re

def valid_email(address):
    """Conservative syntax check, not proof that a mailbox exists."""
    if not isinstance(address,str) or len(address)>254 or any(c.isspace() for c in address):
        return False
    if address.count("@")!=1:
        return False
    local,domain=address.rsplit("@",1)
    if not local or len(local)>64 or not domain or len(domain)>253:
        return False
    if local.startswith(".") or local.endswith(".") or ".." in local:
        return False
    labels=domain.split(".")
    return len(labels)>=2 and all(
        1<=len(label)<=63 and label[0].isalnum() and label[-1].isalnum()
        and all(ch.isalnum() or ch=="-" for ch in label)
        for label in labels
    )

def bounce_evidence(body):
    """Classify delivery evidence without treating arbitrary prose as a DSN.

    Returns (status, explanation). This is an advisory, fail-closed result:
    no classification verifies an address or authorizes outreach.
    """
    if not isinstance(body, str) or not body.strip():
        return ("needs_manual_review", "Missing delivery diagnostic")
    # Bound work on pasted mail bodies. Headers and diagnostics normally precede
    # quoted historical messages; scanning the entire thread risks false matches.
    text = body[:12000].lower()
    # Explicit permanent recipient failures outrank generic temporary language.
    if re.search(r"(?<![0-9])(?:550\\s+)?5\\.1\\.[01](?![0-9])", text) or any(
        phrase in text for phrase in (
            "user does not exist", "address does not exist",
            "recipient not found", "account that you tried to reach does not exist",
            "address locked or deactivated"
        )
    ):
        return ("suppress_permanent", "Recipient address reported unavailable")
    if re.search(r"(?<![0-9])5\\.4\\.1(?![0-9])", text) or any(
        phrase in text for phrase in (
            "recipient address rejected", "message blocked", "policy that",
            "554.5.7.1"
        )
    ):
        return ("suppress_rejected", "Delivery rejected by recipient or policy")
    if re.search(r"(?<![0-9])4\\.[0-9]\\.[0-9]{1,2}(?![0-9])", text) or any(
        phrase in text for phrase in (
            "dns error", "timed out", "delivery incomplete",
            "relay access denied", "remote server is misconfigured"
        )
    ):
        return ("hold_for_verification", "Temporary or uncertain delivery failure")
    return ("needs_manual_review", "Unrecognized delivery diagnostic")


def classify_bounce(body):
    """Compatibility wrapper used by CRM imports."""
    return bounce_evidence(body)[0]

def summarize_bounces(messages):
    """Return statuses for full bounce bodies; duplicate notices collapse by address.

    messages: iterable of dicts with recipient and body keys. Do not pass
    marketing copy as bounce evidence. No external requests are performed.
    """
    priority={"needs_manual_review":0,"hold_for_verification":1,"suppress_rejected":2,"suppress_permanent":3}
    result={}
    for message in messages:
        if not isinstance(message, dict):\n            continue\n        email=message.get("recipient")\n        if not isinstance(email, str):\n            continue\n        email=email.strip().lower()
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
    if not isinstance(address, str) or not isinstance(suppression_statuses, dict):\n        return False\n    return valid_email(address.strip().lower()) and suppression_statuses.get(address.strip().lower())=="verified_clear"
