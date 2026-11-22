"""V77 portable export manifest builder. No I/O, auth, or deletion.

Caller must authorize tenant access and generate/validate export bytes separately.
"""
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone

NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
MAX_FILES = 100
MAX_BYTES = 100 * 1024 * 1024

@dataclass(frozen=True)
class ExportPart:
    filename: str
    content: bytes
    records: int

def build_manifest(workspace_id, parts, created_at):
    if not isinstance(workspace_id, str) or not workspace_id.strip():
        raise ValueError("workspace required")
    if not isinstance(created_at, datetime) or created_at.tzinfo is None:
        raise ValueError("timezone-aware created_at required")
    if not isinstance(parts, (tuple, list)) or not 1 <= len(parts) <= MAX_FILES:
        raise ValueError("invalid parts count")
    seen = set()
    total = 0
    items = []
    for part in parts:
        if not isinstance(part, ExportPart):
            raise ValueError("invalid part")
        if not isinstance(part.filename, str) or not NAME.fullmatch(part.filename):
            raise ValueError("unsafe filename")
        if part.filename.casefold() in seen:
            raise ValueError("duplicate filename")
        seen.add(part.filename.casefold())
        if not isinstance(part.content, bytes):
            raise ValueError("content must be bytes")
        if not isinstance(part.records, int) or isinstance(part.records, bool) or part.records < 0:
            raise ValueError("invalid record count")
        total += len(part.content)
        if total > MAX_BYTES:
            raise ValueError("export exceeds size limit")
        items.append({"filename": part.filename, "bytes": len(part.content),
                      "records": part.records,
                      "sha256": hashlib.sha256(part.content).hexdigest()})
    return {"schema_version": 1, "workspace_id": workspace_id,
            "created_at": created_at.astimezone(timezone.utc).isoformat(),
            "files": items, "total_bytes": total,
            "total_records": sum(p.records for p in parts),
            "scope": "caller-supplied parts only; completeness not independently verified",
            "warning": "Hash checks integrity, not authenticity or authorization."}

def verify_manifest(manifest, parts):
    """Verify exact filenames, sizes, counts and SHA256 digests, not source completeness."""
    if not isinstance(manifest, dict) or not isinstance(parts, (tuple, list)):
        return False
    try:
        rebuilt = build_manifest(manifest["workspace_id"], parts,
                                 datetime.fromisoformat(manifest["created_at"]))
    except (ValueError, TypeError, KeyError):
        return False
    return rebuilt == manifest
