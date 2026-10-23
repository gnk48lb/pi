import os
import shutil
import sqlite3
import tempfile
import unittest

from bookshop import db


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "shop.sqlite3")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_migrate_is_idempotent(self):
        conn = db.connect(self.path)
        first = db.migrate(conn)
        self.assertEqual(first, [v for v, _ in db.available()])
        self.assertEqual(db.migrate(conn), [])
        self.assertEqual(db.current_version(conn), db.available()[-1][0])

    def test_target_stops_early_and_resumes(self):
        conn = db.connect(self.path)
        self.assertEqual(db.migrate(conn, target=1), [1])
        self.assertEqual(db.current_version(conn), 1)
        self.assertEqual(db.migrate(conn)[0], 2)

    def test_failed_migration_is_rolled_back(self):
        migrations = os.path.join(self.dir, "migrations")
        os.mkdir(migrations)
        with open(os.path.join(migrations, "001_a.sql"), "w") as fh:
            fh.write("CREATE TABLE a (x);")
        with open(os.path.join(migrations, "002_bad.sql"), "w") as fh:
            fh.write("CREATE TABLE b (x);\nCREATE TABLE a (y);")           # `a` exists already
        old, db.MIGRATIONS_DIR = db.MIGRATIONS_DIR, migrations
        try:
            conn = db.connect(self.path)
            with self.assertRaises(sqlite3.OperationalError):
                db.migrate(conn)
            self.assertEqual(db.current_version(conn), 1)
            tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
            self.assertNotIn("b", tables)
        finally:
            db.MIGRATIONS_DIR = old


if __name__ == "__main__":
    unittest.main()
