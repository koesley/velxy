"""Dependency-aware readiness probe; no secrets or upstream details in responses."""
def check(database_probe=None, storage_probe=None):
    if database_probe is None:
        from verify_database import check as database_probe
    if storage_probe is None:
        from verify_storage import check as storage_probe
    try:
        return database_probe() == "connected" and storage_probe() == "connected"
    except Exception:
        return False
