"""GENESIS FORGE: deterministic, tenant-scoped workspace application blueprints.

No arbitrary code execution, external effects, or production publishing.
Only allowlisted components may be compiled into a preview manifest.
"""
import hashlib
import json
import re

COMPONENTS = {
    "crm": {"label": "Customer CRM", "permissions": ["leads:read"]},
    "tasks": {"label": "Job Tracking", "permissions": ["tasks:read"]},
    "schedule": {"label": "Scheduling", "permissions": ["tasks:read"]},
    "quotes": {"label": "Quotes", "permissions": ["quotes:read"]},
    "outcomes": {"label": "Outcome Reporting", "permissions": ["outcomes:read"]},
}
TEMPLATES = {
    "cleaning": ("crm", "schedule", "tasks", "quotes"),
    "construction": ("crm", "tasks", "quotes", "outcomes"),
    "consulting": ("crm", "schedule", "quotes", "outcomes"),
    "general": ("crm", "tasks", "quotes"),
}
SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def compile_blueprint(workspace_id, name, industry="general", components=None):
    """Return a validated, deterministic preview manifest; never deploy."""
    if not isinstance(workspace_id, str) or not SLUG.fullmatch(workspace_id):
        raise ValueError("Invalid workspace ID")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise ValueError("Application name must be 1-100 characters")
    if not isinstance(industry, str) or industry not in TEMPLATES:
        raise ValueError("Unsupported industry")
    if components is None:
        components = TEMPLATES[industry]
    if not isinstance(components, (list, tuple)) or not 1 <= len(components) <= 5:
        raise ValueError("Select 1-5 approved components")
    if any(not isinstance(c, str) or c not in COMPONENTS for c in components):
        raise ValueError("Unknown or unauthorized component")
    if len(set(components)) != len(components):
        raise ValueError("Duplicate component")
    blocks = [{"type": key, **COMPONENTS[key]} for key in components]
    manifest = {
        "schema_version": 1,
        "workspace_id": workspace_id,
        "name": name.strip(),
        "industry": industry,
        "status": "preview_only",
        "components": blocks,
        "required_permissions": sorted({p for b in blocks for p in b["permissions"]}),
        "external_actions_enabled": False,
        "custom_code_enabled": False,
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    manifest["fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return manifest


def validate_manifest(manifest, workspace_id):
    """Fail closed if the preview was tampered with or belongs to another tenant."""
    if not isinstance(manifest, dict) or manifest.get("workspace_id") != workspace_id:
        raise ValueError("Workspace mismatch")
    fingerprint = manifest.get("fingerprint")
    if not isinstance(fingerprint, str):
        raise ValueError("Missing fingerprint")
    reconstructed = compile_blueprint(
        workspace_id, manifest.get("name"), manifest.get("industry"),
        [block["type"] for block in manifest.get("components", [])
        if isinstance(block, dict) and isinstance(block.get("type"), str)])
    if reconstructed != manifest:
        raise ValueError("Invalid or modified blueprint")
    return True
