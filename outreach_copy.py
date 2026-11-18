"""VELXTRIA outreach copy builder: personalized, evidence-based, human-approved drafts.

This module never sends email. Callers must review factual observations before use.
"""
from dataclasses import dataclass
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

def draft(prospect: Prospect, style: str = "bold") -> dict:
    """Return subject/body/verification metadata, not a ready-to-send campaign.

    The observation is only included if a source is supplied; the caller must
    independently confirm it is accurate and appropriate before sending.
    """
    if not prospect.name.strip():
        raise ValueError("Business name is required")
    if style not in ("bold", "curious", "personal"):
        raise ValueError("Unknown outreach style")
    industry = prospect.industry.lower().strip()
    angle = INDUSTRY_ANGLES.get(industry, INDUSTRY_ANGLES["general"])
    greeting = "Hi " + (prospect.first_name.strip() or "there") + ","
    observation = prospect.verified_observation.strip()
    source = prospect.observation_source.strip()
    if observation and not source:
        raise ValueError("An observation source is required to prevent invented personalization")
    subjects = {
        "bold": f"A new opportunity for {prospect.name.strip()}?",
        "curious": f"One question about {prospect.name.strip()}",
        "personal": f"Quick introduction to {prospect.name.strip()}",
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
    msg = message.lower()
    if any(x in msg for x in ("unsubscribe", "remove me", "stop emailing", "do not contact")):
        return "do_not_contact"
    if any(x in msg for x in ("not interested", "no thanks", "already have someone", "have someone else")):
        return "declined"
    if any(x in msg for x in ("tell me more", "interested", "send details", "schedule a call")):
        return "potential_interest"
    return "needs_review"
