"""V82: read-only lead quality inspector for VELXTRIA Business OS.

The caller must authorize workspace access before invoking this function.
"""
import re

EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

def inspect_leads(connection, workspace_id, limit=500):
    if not isinstance(workspace_id, str) or not workspace_id.strip():
        raise ValueError("workspace_id required")
    if type(limit) is not int or not 1 <= limit <= 2000:
        raise ValueError("limit out of range")
    rows = connection.execute(
        "SELECT id,name,contact,status FROM bos59_leads "
        "WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT ?",
        (workspace_id, limit + 1)
    ).fetchall()
    truncated = len(rows) > limit
    rows = rows[:limit]
    by_contact = {}
    issues = []
    for lead_id, name, contact, status in rows:
        if not isinstance(lead_id, str):
            raise ValueError("invalid lead id")
        normalized = contact.strip().casefold() if isinstance(contact, str) else ""
        flags = []
        if not isinstance(name, str) or not name.strip():
            flags.append("missing_name")
        if not normalized or not EMAIL.fullmatch(normalized):
            flags.append("invalid_contact_email")
        elif normalized in by_contact:
            flags.append("duplicate_contact_in_sample")
        else:
            by_contact[normalized] = lead_id
        if status not in ("new", "contacted", "won", "lost"):
            flags.append("unknown_status")
        if flags:
            issues.append({"lead_id": lead_id, "flags": flags})
    return {
        "workspace_id": workspace_id, "inspected": len(rows),
        "sample_truncated": truncated, "flagged": len(issues),
        "issues": issues,
        "notice": "Read-only sample. Duplicate detection is limited to inspected leads; no records are modified."
    }
