"""Offline regression tests for PostgreSQL deployment URL validation."""
import unittest
from deployment_readiness_v43 import valid_postgres_url


class PostgresURLTests(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(valid_postgres_url("postgresql://app:secret@db.example.com:5432/app"))
        self.assertTrue(valid_postgres_url("postgres://app:secret@db.example.com/app?sslmode=require"))
        self.assertTrue(valid_postgres_url("postgresql://app:p%40ss@db.example.com:5432/app"))

    def test_invalid(self):
        for value in (
            "", "postgresql://", "postgresql://db.example.com/app",
            "postgresql://app@db.example.com/app",
            "postgresql://app:secret@/app",
            "postgresql://app:secret@db.example.com:invalid/app",
            "postgresql://app:secret@db.example.com:99999/app",
            "postgresql://app:secret@db.example.com/app\n",
            " postgresql://app:secret@db.example.com/app",
            "https://app:secret@db.example.com/app",
            "postgresql://app:secret@db.example.com/app?password=leak",
            "postgresql://app:secret@db.example.com",
            "postgresql://app:secret@db.example.com/",
            "postgresql://app:secret@db.example.com/app#fragment",
            "postgresql://app:secret@db.example.com/app ",
            "postgresql://app:secret@db.example.com/app/extra",
        ):
            with self.subTest(value=value.split("@")[-1]):
                self.assertFalse(valid_postgres_url(value))


if __name__ == "__main__":
    unittest.main()
