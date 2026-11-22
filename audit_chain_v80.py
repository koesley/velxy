"""V80 standalone tenant-scoped tamper-evident audit chain verification.

Not a database integration. Callers must authorize event access and provide
complete ordered records from a trusted source.
"""
import hashlib
import json
from dataclasses import dataclass

GENESIS = "0" * 64

@dataclass(frozen=True)
class AuditEvent:
    workspace_id: str
    sequence: int
    actor_id: str
    action: str
    target_id: str
    occurred_at: str

def _payload(event):
    if not isinstance(event, AuditEvent):
        raise ValueError("invalid event")
    if type(event.sequence) is not int or event.sequence < 1:
        raise ValueError("invalid sequence")
    for value in (event.workspace_id, event.actor_id, event.action, event.target_id, event.occurred_at):
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            raise ValueError("invalid audit field")
    return {"workspace_id": event.workspace_id, "sequence": event.sequence,
            "actor_id": event.actor_id, "action": event.action,
            "target_id": event.target_id, "occurred_at": event.occurred_at}

def append_hash(previous_hash, event):
    if not isinstance(previous_hash, str) or len(previous_hash) != 64 or any(c not in "0123456789abcdef" for c in previous_hash):
        raise ValueError("invalid previous hash")
    payload = json.dumps(_payload(event), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256((previous_hash + ":" + payload).encode("utf-8")).hexdigest()

def build_chain(workspace_id, events):
    if not isinstance(workspace_id, str) or not workspace_id.strip():
        raise ValueError("invalid workspace")
    if not isinstance(events, (tuple, list)) or len(events) > 10000:
        raise ValueError("invalid event collection")
    previous = GENESIS
    rows = []
    for index, event in enumerate(events, 1):
        if event.workspace_id != workspace_id or event.sequence != index:
            raise ValueError("tenant mismatch or sequence gap")
        digest = append_hash(previous, event)
        rows.append({"event": event, "previous_hash": previous, "hash": digest})
        previous = digest
    return rows

def verify_chain(workspace_id, rows, expected_head):
    """Reject modifications/gaps. Anchor expected_head independently for deletion detection."""
    if not isinstance(expected_head, str) or len(expected_head) != 64:
        return False
    if not isinstance(rows, (list, tuple)) or len(rows) > 10000:
        return False
    previous = GENESIS
    try:
        for index, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                return False
            event = row["event"]
            if event.workspace_id != workspace_id or event.sequence != index:
                return False
            if row["previous_hash"] != previous:
                return False
            calculated = append_hash(previous, event)
            if row["hash"] != calculated:
                return False
            previous = calculated
    except (ValueError, TypeError, KeyError, AttributeError):
        return False
    return previous == expected_head
