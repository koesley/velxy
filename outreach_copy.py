"""VELXTRIA outreach copy builder: personalized, evidence-based, human-approved drafts.

This module never sends email. Callers must review factual observations before use.
"""
from dataclasses import dataclass
import re
from typing import Optional

@dataclass(frozen=True)
class Prospect:
    name: str
    industry: str
    first_name: str = ""
    verified_observation: str = ""
    observation_source: str = ""

INDUSTRY_ANGLES = {
    "restaurant": "turning more inquiries into reservations and repeat visits",
    "retail": "understanding which customer opportunities deserve attention",
    "construction": "following up on estimates and keeping potential projects moving",
    "service": "responding to inquiries and reducing repetitive administrative work",
    "general": "spotting overlooked opportunities and simplifying everyday operations",
}

def _safe_field(value: str, label: str, limit: int) -> str:
    """Bound prospect-controlled text and reject header/control injection."""
    if not isinstance(value, str):
        raise ValueError(label + " must be text")
    value = value.strip()
    if len(value) > limit:
        raise ValueError(label + " is too long")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(label + " contains control characters")
    return value


def _safe_observation(value: str) -> str:
    """Allow ordinary punctuation, but not line breaks or fabricated long claims."""
    return _safe_field(value, "Observation", 500)


def draft(prospect: Prospect, style: str = "bold") -> dict:
    """Return subject/body/verification metadata, not a ready-to-send campaign.

    The observation is only included if a source is supplied; the caller must
    independently confirm it is accurate and appropriate before sending.
    """
    name = _safe_field(prospect.name, "Business name", 120)
    first_name = _safe_field(prospect.first_name, "Contact name", 80)
    industry_name = _safe_field(prospect.industry, "Industry", 80)
    observation = _safe_observation(prospect.verified_observation)
    source = _safe_field(prospect.observation_source, "Observation source", 300)
    if not name:
        raise ValueError("Business name is required")
    if style not in ("bold", "curious", "personal"):
        raise ValueError("Unknown outreach style")
    industry = industry_name.lower()
    angle = INDUSTRY_ANGLES.get(industry, INDUSTRY_ANGLES["general"])
    greeting = "Hi " + (first_name or "there") + ","
    if observation and not source:
        raise ValueError("An observation source is required to prevent invented personalization")
    subjects = {
        "bold": f"A new opportunity for {name}?",
        "curious": f"One question about {name}",
        "personal": f"Quick introduction to {name}",
    }
    openings = {
        "bold": "The next advantage for a business might be hiding in work it already does every day.",
        "curious": "I had a question about where your next business opportunity might come from.",
        "personal": "I'm reaching out personally because we're building something for small businesses.",
    }
    lines = [greeting, "", openings[style]]
    if observation:
        lines += ["", f"One thing I noticed: {observation}"]
    lines += [
        "",
        f"At VELXTRIA, we're building AI-powered tools designed to help businesses with {angle}.",
        "I don't want to assume this is a priority for you, but I'd love to learn whether it could be useful.",
        "",
        "Would you be open to a quick look or a short conversation?",
        "",
        "— VELXTRIA",
    ]
    return {
        "subject": subjects[style],
        "body": "\n".join(lines),
        "requires_human_review": True,
        "observation_source": source or None,
        "style": style,
        "industry_angle": angle,
    }

def classify_reply(message: str) -> str:
    """Conservative manual-triage hint; never automatically follow up."""
    if not isinstance(message, str):
        raise ValueError("Reply must be text")
    # Only classify the sender's latest reply, not quoted earlier messages.
    # Common reply headers and quote prefixes are not current consent.
    current = []
    for line in message[:20000].splitlines():
        stripped = line.strip()
        if stripped.startswith(">") or re.match(r"On .+ wrote:\s*$", stripped, re.I):
            break
        if stripped.lower().startswith(("from:", "original message", "-----original message")):
            break
        current.append(line)
    msg = " ".join(current).lower()
    if any(x in msg for x in ("unsubscribe", "remove me", "stop emailing", "do not contact",
                               "don't contact", "stop contacting", "take me off",
                               "opt out", "opt-out", "no more emails")):
        return "do_not_contact"
    if any(x in msg for x in ("not interested", "no thanks", "no thank you",
                               "already have someone", "have someone else",
                               "not right now", "not a priority")):
        return "declined"
    if any(x in msg for x in ("tell me more", "i'm interested", "i am interested",
                               "send details", "schedule a call", "book a call")):
        return "potential_interest"
    return "needs_review"

def reply_guidance(message: str) -> dict:
    """Suggest a respectful response strategy without sending any email."""
    classification = classify_reply(message)
    guidance = {
        "do_not_contact": ("Do not send another marketing message.", ""),
        "declined": ("Mark as declined and do not continue pitching.", ""),
        "potential_interest": ("Respond personally with a concrete next step.", "Thanks for your interest. What part of your business would you most like to improve? I can share a focused VELXTRIA walkthrough."),
        "needs_review": ("Read the full reply and decide manually.", ""),
    }
    action, suggestion = guidance[classification]
    return {"classification": classification, "recommended_action": action, "suggested_reply": suggestion, "automatic_send": False}

def quality_check(prospect: Prospect, result: dict) -> dict:
    """Identify missing personalization and unverifiable sales claims."""
    warnings = []
    if not prospect.first_name.strip():
        warnings.append("Contact name missing; greeting is generic.")
    if not prospect.verified_observation.strip():
        warnings.append("No verified business-specific observation supplied.")
    if prospect.verified_observation.strip() and not prospect.observation_source.strip():
        warnings.append("Observation needs a source.")
    body = result.get("body", "").lower()
    for claim in ("guaranteed revenue", "double your sales", "your competitors already use"):
        if claim in body:
            warnings.append("Potentially unsubstantiated claim: " + claim)
    return {"ready_for_review": True, "warnings": warnings, "send_automatically": False}
