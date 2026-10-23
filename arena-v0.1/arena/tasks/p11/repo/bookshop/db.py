"""SQLite connection and a tiny migration runner.

Migrations are the files in bookshop/migrations named NNN_description.sql.  They are applied in the order of NNN, each
one inside its own transaction (do not put BEGIN/COMMIT in them), and recorded in the table schema_migrations.  An
applied migration is never edited: every schema change is a new file.
"""
import os
import re
import sqlite3

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")
_NAME = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def available():
    """[(version, filename), ...] of all migration files, sorted by version."""
    found = []
    for name in sorted(os.listdir(MIGRATIONS_DIR)):
        match = _NAME.match(name)
        if match:
            found.append((int(match.group(1)), name))
    return found


def current_version(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    conn.commit()
    return conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] or 0


def migrate(conn, target=None):
    """Apply the pending migrations (only those up to version `target` when it is given).

    Returns the list of versions that were applied."""
    done = current_version(conn)
    applied = []
    for version, name in available():
        if version <= done or (target is not None and version > target):
            continue
        with open(os.path.join(MIGRATIONS_DIR, name), encoding="utf-8") as fh:
            script = fh.read()
        try:
            conn.executescript("BEGIN;\n%s\nINSERT INTO schema_migrations (version, name) VALUES (%d, '%s');\nCOMMIT;"
                               % (script, version, name))
        except Exception:
            conn.rollback()
            raise
        applied.append(version)
    return applied
