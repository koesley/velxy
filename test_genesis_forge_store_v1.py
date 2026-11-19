"""Persistence and isolation regression tests for Genesis Forge."""
import sqlite3
import unittest
from genesis_forge_store_v1 import save, load, list_previews


class GenesisForgeStorageTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")

    def tearDown(self):
        self.db.close()

    def test_create_and_load(self):
        key, rev = save(self.db, "tenant_a", 1, "Cleaning", "cleaning")
        self.assertEqual(rev, 1)
        self.assertEqual(load(self.db, "tenant_a", 1, key)["manifest"]["industry"], "cleaning")

    def test_tenant_isolation(self):
        key, _ = save(self.db, "tenant_a", 1, "Cleaning")
        for workspace, owner in (("tenant_b", 1), ("tenant_a", 2)):
            with self.subTest(workspace=workspace, owner=owner):
                with self.assertRaises(ValueError):
                    load(self.db, workspace, owner, key)
                self.assertEqual(list_previews(self.db, workspace, owner), [])

    def test_revision_conflict(self):
        key, _ = save(self.db, "tenant_a", 1, "First")
        _, revision = save(self.db, "tenant_a", 1, "Second",
                           preview_id=key, expected_revision=1)
        self.assertEqual(revision, 2)
        with self.assertRaises(ValueError):
            save(self.db, "tenant_a", 1, "Stale",
                 preview_id=key, expected_revision=1)
        self.assertEqual(load(self.db, "tenant_a", 1, key)["manifest"]["name"], "Second")

    def test_update_scope_enforced(self):
        key, _ = save(self.db, "tenant_a", 1, "First")
        with self.assertRaises(ValueError):
            save(self.db, "tenant_a", 2, "Unauthorized",
                 preview_id=key, expected_revision=1)
        with self.assertRaises(ValueError):
            save(self.db, "tenant_b", 1, "Unauthorized",
                 preview_id=key, expected_revision=1)

    def test_tampered_stored_manifest_fails_closed(self):
        key, _ = save(self.db, "tenant_a", 1, "First")
        self.db.execute("UPDATE genesis_previews SET manifest_json=? WHERE id=?",
                        ('{"workspace_id":"tenant_a"}', key))
        with self.assertRaises(ValueError):
            load(self.db, "tenant_a", 1, key)

    def test_list_only_owned_previews(self):
        key, _ = save(self.db, "tenant_a", 1, "First")
        save(self.db, "tenant_a", 2, "Second")
        rows = list_previews(self.db, "tenant_a", 1)
        self.assertEqual([r["id"] for r in rows], [key])


if __name__ == "__main__":
    unittest.main()
