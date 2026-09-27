"""Disposable SQLite fixtures for headless (no GUI) tests.

Contract (enforced everywhere in this suite):

* Every database lives in a per-test temporary directory created with
  ``tempfile.mkdtemp`` and removed on teardown.
* Databases are created and seeded EXCLUSIVELY through the public
  ``Database`` API (``add_group`` / ``add_child`` / ``add_vaccination`` ...).
* The tracked production databases ``kindergarten.db`` and ``123.db`` are
  NEVER opened, copied, or otherwise touched.
"""

import os
import shutil
import tempfile
from datetime import datetime, timedelta

from database import Database


def make_db(prefix="kgh_test_"):
    """Create a brand-new disposable ``Database`` in a temp directory.

    Returns ``(db, tmpdir)``. The caller MUST call ``dispose_db`` on teardown.
    """
    tmpdir = tempfile.mkdtemp(prefix=prefix)
    db_path = os.path.join(tmpdir, "test_kindergarten.db")
    return Database(db_path), tmpdir


def dispose_db(db, tmpdir):
    """Close the database and remove its temp directory."""
    try:
        db.close()
    except Exception:
        pass
    shutil.rmtree(tmpdir, ignore_errors=True)


def seed_groups(db, names):
    """Create groups by name through the public API.

    Returns a ``{name: id}`` mapping rebuilt from ``get_groups()`` so callers
    receive the real primary keys rather than relying on lastrowid state.
    """
    for name in names:
        db.add_group(name)
    return {row["name"]: row["id"] for row in db.get_groups()}


def iso_days_ago(days):
    """ISO ``YYYY-MM-DD`` date string for ``days`` days before today."""
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")


def make_unversioned_db(prefix="kgh_baseline_", db_name="baseline.db"):
    """Create a disposable baseline database with ``PRAGMA user_version = 0``.

    Simulates a database written by an older, pre-versioning build: it carries
    exactly the current six-table schema plus optional seeded rows, but its
    recorded schema version is 0. The file is created through the real
    ``Database`` API and then downgraded to version 0, so the schema is
    guaranteed to match the live one (no hand-copied SQL that could drift).

    Returns ``(db_path, tmpdir)``. Optionally pass ``rows=True`` to seed one
    synthetic group/child pair before downgrading, so adoption tests can prove
    pre-existing data survives.
    """
    return _make_legacy(prefix, db_name, rows=False)


def make_legacy_schema_db(
    prefix="kgh_legacy_", db_name="legacy.db", user_version=0, rows=False
):
    """Create a disposable DB with the six-table schema and an explicit
    ``user_version`` (defaults to 0, i.e. the pre-versioning baseline).

    ``rows=True`` also seeds one synthetic group and one child through the
    public ``Database`` API before the version is (re)set.
    """
    return _make_legacy(prefix, db_name, rows=rows, user_version=user_version)


def _make_legacy(prefix, db_name, rows=False, user_version=0):
    from database import Database

    tmpdir = tempfile.mkdtemp(prefix=prefix)
    db_path = os.path.join(tmpdir, db_name)
    db = Database(db_path)
    try:
        if rows:
            db.add_group("Малыши")
            db.add_child("Тестов Тест", "2020-01-01", 1)
        # Downgrade to the pre-versioning baseline. This deliberately bypasses
        # the migration framework: the fixture must *look* like a legacy file,
        # not migrate itself.
        set_user_version(db, user_version)
    finally:
        db.close()
    return db_path, tmpdir


def user_version_of(db):
    """Read ``PRAGMA user_version`` of an open ``Database`` connection."""
    return db.cursor.execute("PRAGMA user_version").fetchone()[0]


def set_user_version(db, version):
    """Set ``PRAGMA user_version`` on an open ``Database`` connection."""
    db.cursor.execute("PRAGMA user_version = %d" % version)
    db.conn.commit()


def table_names(db):
    """Sorted list of user-table names of an open ``Database`` connection.

    SQLite's internal bookkeeping tables (``sqlite_sequence`` etc.) are
    excluded: they are not part of the schema this project defines.
    """
    rows = db.cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite\\_%' ESCAPE '\\' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]
