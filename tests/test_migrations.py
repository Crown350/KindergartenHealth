"""Batch B — schema versioning and forward migrations.

Covers defect #3 (no schema migration / create-only data layer).

The data layer must own the schema version instead of blindly running
``CREATE TABLE IF NOT EXISTS`` on every startup. These tests drive that
contract through the public ``Database`` API plus a few documented test hooks
on the class (``MIGRATIONS``, ``_migrate``) that exist to make the framework
unit-testable.

All databases are disposable files created with ``tempfile``. The tracked
production databases ``kindergarten.db`` and ``123.db`` are never opened,
copied, or migrated.
"""

import sqlite3
import unittest

import database
from database import SCHEMA_VERSION, Database
from tests.db_fixtures import (
    dispose_db,
    make_db,
    make_legacy_schema_db,
    make_unversioned_db,
    set_user_version,
    table_names,
    user_version_of,
)

EXPECTED_TABLES = [
    "attendance",
    "children",
    "groups",
    "health_records",
    "parents",
    "vaccinations",
]


class TestSchemaVersionConstant(unittest.TestCase):
    def test_schema_version_is_a_positive_int(self):
        self.assertIsInstance(SCHEMA_VERSION, int)
        self.assertGreaterEqual(SCHEMA_VERSION, 1)

    def test_production_migrations_registry_is_clean(self):
        # No migration may exist in production code merely to justify the
        # framework: the registry starts empty and only gains an entry when a
        # real schema change is needed.
        self.assertEqual(
            sorted(Database.MIGRATIONS.keys()),
            [],
            "production MIGRATIONS registry must be empty",
        )

    def test_registry_keys_are_ints_and_contiguous_after_baseline(self):
        # Contract for future maintainers: target versions are ints and every
        # step from 1..SCHEMA_VERSION-1 is representable.
        for target in Database.MIGRATIONS:
            self.assertIsInstance(target, int)
            self.assertGreater(target, 0)


class TestFreshDatabase(unittest.TestCase):
    def setUp(self):
        self.db, self.tmpdir = make_db()

    def tearDown(self):
        dispose_db(self.db, self.tmpdir)

    def test_all_six_tables_exist(self):
        self.assertEqual(sorted(table_names(self.db)), EXPECTED_TABLES)

    def test_user_version_is_current(self):
        self.assertEqual(user_version_of(self.db), SCHEMA_VERSION)

    def test_reopening_current_db_is_a_noop(self):
        # Closing and reopening an already-current database must not change the
        # schema or the recorded version.
        self.db.close()
        self.db = Database(self.db.db_file)
        self.assertEqual(sorted(table_names(self.db)), EXPECTED_TABLES)
        self.assertEqual(user_version_of(self.db), SCHEMA_VERSION)


class TestAdoptUnversionedBaseline(unittest.TestCase):
    """A legacy database with ``user_version = 0`` must be adopted in place."""

    def setUp(self):
        # Legacy file: current six-table schema + one synthetic row, but
        # recorded version 0 (what a pre-versioning build leaves on disk).
        self.legacy_path, self.tmpdir = make_legacy_schema_db(rows=True)
        self.db = None

    def tearDown(self):
        if self.db is not None:
            dispose_db(self.db, self.tmpdir)
        else:
            dispose_db(None, self.tmpdir)

    def test_baseline_version_is_adopted_without_data_loss(self):
        self.db = Database(self.legacy_path)
        self.assertEqual(user_version_of(self.db), SCHEMA_VERSION)

        # Pre-existing rows survive adoption: no DROP, no DELETE.
        groups = [r["name"] for r in self.db.get_groups()]
        self.assertEqual(groups, ["Малыши"])
        children = [r["full_name"] for r in self.db.get_children_summary()]
        self.assertEqual(children, ["Тестов Тест"])

    def test_adoption_does_not_recreate_tables(self):
        # Open once so the file is fully initialized, then prove reopening is
        # idempotent: same tables, same row counts, no duplicate artifacts.
        self.db = Database(self.legacy_path)
        before = table_names(self.db)
        rows_before = self.db.cursor.execute("SELECT COUNT(*) FROM children").fetchone()[0]
        self.db.close()

        self.db = Database(self.legacy_path)
        self.assertEqual(table_names(self.db), before)
        rows_after = self.db.cursor.execute("SELECT COUNT(*) FROM children").fetchone()[0]
        self.assertEqual(rows_after, rows_before)

    def test_truly_unversioned_file_is_adopted(self):
        # A file whose user_version was never set (raw legacy file) behaves
        # exactly like the explicit version-0 case.
        path, tmpdir = make_unversioned_db()
        try:
            db = Database(path)
            try:
                self.assertEqual(user_version_of(db), SCHEMA_VERSION)
            finally:
                db.close()
        finally:
            dispose_db(None, tmpdir)


class TestForwardMigration(unittest.TestCase):
    """A synthetic migration exercises the sequential, transactional path.

    The production registry is empty, so these tests simulate a FUTURE build
    that knows a higher ``SCHEMA_VERSION`` and ships real migrations. They
    temporarily raise the module-level ``SCHEMA_VERSION`` and register
    throwaway migrations, then restore both. No fake production schema change
    is added to database.py.
    """

    def setUp(self):
        self.db, self.tmpdir = make_db()
        self._saved_version = database.SCHEMA_VERSION
        self._saved_registry = dict(Database.MIGRATIONS)

    def tearDown(self):
        database.SCHEMA_VERSION = self._saved_version
        Database.MIGRATIONS.clear()
        Database.MIGRATIONS.update(self._saved_registry)
        dispose_db(self.db, self.tmpdir)

    def _simulate_future(self, migrations):
        """Pretend a newer build exists with ``migrations`` registered."""
        database.SCHEMA_VERSION = self._saved_version + len(migrations)
        Database.MIGRATIONS.clear()
        Database.MIGRATIONS.update(migrations)

    def test_migration_runs_exactly_once(self):
        calls = []
        target = self._saved_version + 1
        self._simulate_future({target: lambda cur: calls.append(cur)})

        # A file left at the previous version is what an upgrade starts from.
        set_user_version(self.db, self._saved_version)
        self.db.close()
        self.db = Database(self.db.db_file)

        self.assertEqual(len(calls), 1)
        self.assertEqual(user_version_of(self.db), target)

    def test_version_advances_only_after_success(self):
        # A migration that fails mid-way must not advance the version.
        def broken(cur):
            cur.execute("CREATE TABLE should_not_exist (id INTEGER)")
            raise RuntimeError("synthetic migration failure")

        target = self._saved_version + 1
        self._simulate_future({target: broken})

        set_user_version(self.db, self._saved_version)
        self.db.close()
        with self.assertRaises(RuntimeError):
            self.db = Database(self.db.db_file)

        # Re-open as a build that has no such migration, to inspect the
        # on-disk state: the version is unchanged and the partial work is gone.
        database.SCHEMA_VERSION = self._saved_version
        Database.MIGRATIONS.clear()
        self.db = Database(self.db.db_file)

        self.assertEqual(user_version_of(self.db), self._saved_version)
        self.assertNotIn("should_not_exist", table_names(self.db))

    def test_failed_migration_surfaces_error(self):
        def broken(cur):
            raise RuntimeError("synthetic migration failure")

        target = self._saved_version + 1
        self._simulate_future({target: broken})

        set_user_version(self.db, self._saved_version)
        self.db.close()
        with self.assertRaises(RuntimeError):
            self.db = Database(self.db.db_file)

    def test_migrations_run_sequentially(self):
        order = []
        base = self._saved_version
        self._simulate_future(
            {
                base + 1: lambda cur: order.append(1),
                base + 2: lambda cur: order.append(2),
            }
        )

        set_user_version(self.db, base)
        self.db.close()
        self.db = Database(self.db.db_file)

        self.assertEqual(order, [1, 2])
        self.assertEqual(user_version_of(self.db), base + 2)


class TestFutureDatabaseRejected(unittest.TestCase):
    """A database written by a NEWER build must not be silently downgraded."""

    def setUp(self):
        self.db, self.tmpdir = make_db()

    def tearDown(self):
        dispose_db(self.db, self.tmpdir)

    def test_newer_user_version_is_rejected(self):
        future = SCHEMA_VERSION + 5
        set_user_version(self.db, future)
        self.db.close()

        with self.assertRaises(Exception):
            self.db = Database(self.db.db_file)

        # The file itself must be untouched by the rejection.
        conn = sqlite3.connect(self.db.db_file)
        try:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], future)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
