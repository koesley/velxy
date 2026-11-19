"""GENESIS FORGE preview storage with tenant isolation and optimistic revisions.

This module never publishes or executes generated applications.
Caller must authenticate and authorize workspace membership before invoking.
"""
import json
import secrets
import time
from genesis_forge_v1 import compile_blueprint, validate_manifest


def setup(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS genesis_previews (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        owner_id INTEGER NOT NULL,
        revision INTEGER NOT NULL,
        manifest_json TEXT NOT NULL,
        created INTEGER NOT NULL,
        updated INTEGER NOT NULL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS genesis_previews_scope ON genesis_previews(workspace_id, owner_id, updated)")


def save(conn, workspace_id, owner_id, name, industry="general", components=None,
         preview_id=None, expected_revision=None):
    """Save a preview only; enforce owner and workspace scoping on updates."""
    if not isinstance(owner_id, int) or isinstance(owner_id, bool) or owner_id <= 0:
        raise ValueError("Invalid owner")
    manifest = compile_blueprint(workspace_id, name, industry, components)
    setup(conn)
    now = int(time.time())
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    with conn:
        if preview_id is None:
            if expected_revision is not None:
                raise ValueError("Revision supplied for new preview")
            preview_id = secrets.token_hex(16)
            conn.execute("INSERT INTO genesis_previews VALUES (?,?,?,?,?,?,?)",
                         (preview_id, workspace_id, owner_id, 1, payload, now, now))
            return preview_id, 1
        if not isinstance(preview_id, str) or len(preview_id) != 32:
            raise ValueError("Invalid preview ID")
        if not isinstance(expected_revision, int) or isinstance(expected_revision, bool) or expected_revision < 1:
            raise ValueError("Expected revision required")
        result = conn.execute(
            "UPDATE genesis_previews SET manifest_json=?,revision=revision+1,updated=? "
            "WHERE id=? AND workspace_id=? AND owner_id=? AND revision=?",
            (payload, now, preview_id, workspace_id, owner_id, expected_revision))
        if result.rowcount != 1:
            raise ValueError("Preview missing, unauthorized, or stale revision")
        return preview_id, expected_revision + 1


def load(conn, workspace_id, owner_id, preview_id):
    """Load a preview only for its owning user in its workspace."""
    if not isinstance(owner_id, int) or isinstance(owner_id, bool) or owner_id <= 0:
        raise ValueError("Invalid owner")
    if not isinstance(workspace_id, str) or not isinstance(preview_id, str):
        raise ValueError("Invalid scope")
    setup(conn)
    row = conn.execute(
        "SELECT revision,manifest_json FROM genesis_previews "
        "WHERE id=? AND workspace_id=? AND owner_id=?",
        (preview_id, workspace_id, owner_id)).fetchone()
    if row is None:
        raise ValueError("Preview not found")
    manifest = json.loads(row[1])
    validate_manifest(manifest, workspace_id)
    return {"id": preview_id, "revision": row[0], "manifest": manifest}


def list_previews(conn, workspace_id, owner_id, limit=50):
    """List owned preview metadata without returning other tenants' data."""
    if not isinstance(owner_id, int) or isinstance(owner_id, bool) or owner_id <= 0:
        raise ValueError("Invalid owner")
    if not isinstance(workspace_id, str):
        raise ValueError("Invalid scope")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError("Invalid limit")
    setup(conn)
    rows = conn.execute(
        "SELECT id,revision,manifest_json,updated FROM genesis_previews "
        "WHERE workspace_id=? AND owner_id=? ORDER BY updated DESC,id DESC LIMIT ?",
        (workspace_id, owner_id, limit)).fetchall()
    result = []
    for preview_id, revision, payload, updated in rows:
        manifest = json.loads(payload)
        validate_manifest(manifest, workspace_id)
        result.append({"id": preview_id, "revision": revision,
                       "name": manifest["name"], "industry": manifest["industry"],
                       "updated": updated})
    return result
