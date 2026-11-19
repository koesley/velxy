"""GENESIS FORGE authenticated service boundary.

This is an application-service layer for portal route integration. It does
not expose routes, publish apps, or grant access based on blueprint content.
"""
import business_os_v59 as business_os
from genesis_forge_store_v1 import save, load, list_previews
from genesis_forge_preview_v1 import render_preview


def _authorize(conn, user_id, workspace_id, write=False):
    """Delegate membership and role checks to VELXTRIA's existing access layer."""
    business_os.core.access(conn, user_id, workspace_id, write=write)


def create_preview(conn, user_id, workspace_id, name, industry="general", components=None):
    _authorize(conn, user_id, workspace_id, write=True)
    preview_id, revision = save(conn, workspace_id, user_id, name, industry, components)
    return {"id": preview_id, "revision": revision}


def update_preview(conn, user_id, workspace_id, preview_id, expected_revision,
                   name, industry="general", components=None):
    _authorize(conn, user_id, workspace_id, write=True)
    preview_id, revision = save(
        conn, workspace_id, user_id, name, industry, components,
        preview_id=preview_id, expected_revision=expected_revision)
    return {"id": preview_id, "revision": revision}


def get_preview(conn, user_id, workspace_id, preview_id):
    _authorize(conn, user_id, workspace_id)
    return load(conn, workspace_id, user_id, preview_id)


def get_preview_html(conn, user_id, workspace_id, preview_id):
    _authorize(conn, user_id, workspace_id)
    record = load(conn, workspace_id, user_id, preview_id)
    return render_preview(record["manifest"], workspace_id)


def get_previews(conn, user_id, workspace_id, limit=50):
    _authorize(conn, user_id, workspace_id)
    return list_previews(conn, workspace_id, user_id, limit)
