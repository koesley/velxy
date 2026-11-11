"""V59 database compatibility helpers for the existing portal's psycopg connection.

Use this module from the V59 service when connecting to PostgreSQL.
This is an adapter, not a complete V59 integration.
"""
import re

_SQLITE_PLACEHOLDER = re.compile(r"\?")

class PostgresV59Connection:
    """Translate positional SQLite placeholders to psycopg placeholders.

    V59 SQL currently contains only positional question-mark parameters.
    The adapter intentionally rejects queries with unbound placeholders and
    does not attempt to translate SQLite DDL.
    """
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, parameters=()):
        if not isinstance(sql, str):
            raise TypeError("SQL must be a string")
        if sql.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP ", "PRAGMA ")):
            raise ValueError("Schema changes must use versioned PostgreSQL migrations")
        if "?" in sql:
            if sql.count("?") != len(parameters):
                raise ValueError("SQL placeholder count does not match parameters")
            sql = _SQLITE_PLACEHOLDER.sub("%s", sql)
        elif parameters and "%s" not in sql:
            raise ValueError("SQL parameters supplied without placeholders")
        cursor = self.connection.cursor()
        cursor.execute(sql, parameters)
        return cursor

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

def ensure_v59_schema(connection):
    """Read-only verification; never create tables on request."""
    names = ("v59_contacts", "v59_deals", "v59_audits",
             "v59_workflows", "v59_runs", "v59_agents", "v59_agent_runs")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = ANY(%s)",
            (list(names),),
        )
        found = {row[0] for row in cursor.fetchall()}
    missing = set(names) - found
    if missing:
        raise RuntimeError("V59 schema migration required: " + ", ".join(sorted(missing)))
