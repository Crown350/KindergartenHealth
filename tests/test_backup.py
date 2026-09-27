"""Batch B — atomic database backup.

Covers defect #6 (backup silently overwrites destination) plus the atomicity
gap in ``Database.backup_db``.

The old implementation copied straight to the final destination with
``shutil.copy2``: a crash or a full disk mid-copy left a half-written file in
place of the user's previous backup. The new contract is write-to-temp then
``os.replace`` within the same directory (so the rename stays on one
filesystem and is atomic), with no open ``NamedTemporaryFile`` handle left
behind on Windows.

Success paths are verified against real files in ``tempfile`` directories.
Mocks are used ONLY to inject failures (copy error, replace error) and are
applied to the module-level ``shutil``/``os`` symbols that database.py uses.
The tracked production databases ``kindergarten.db`` and ``123.db`` are never
used as a source or a destination.
"""

import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

from database import Database
from tests.db_fixtures import dispose_db, make_db, seed_groups


def sha256(path):
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def leftover_temp_files(directory):
    """Temp leftovers produced by the atomic path (if any remain)."""
    names = os.listdir(directory)
    return [n for n in names if n.startswith(".kgh_backup_") or n.endswith(".tmp")]


class TestBackupSuccess(unittest.TestCase):
    def setUp(self):
        self.db, self.tmpdir = make_db()
        seed_groups(self.db, ["Малыши", "Старшая"])
        self.dest_dir = tempfile.mkdtemp(prefix="kgh_dest_")
        self.dest = os.path.join(self.dest_dir, "backup.db")

    def tearDown(self):
        dispose_db(self.db, self.tmpdir)
        shutil.rmtree(self.dest_dir, ignore_errors=True)

    def test_backup_bytes_equal_source(self):
        self.assertTrue(self.db.backup_db(self.dest))
        self.assertTrue(os.path.exists(self.dest))
        self.assertEqual(sha256(self.dest), sha256(self.db.db_file))

    def test_backup_is_a_valid_sqlite_db(self):
        self.assertTrue(self.db.backup_db(self.dest))
        conn = sqlite3.connect(self.dest)
        try:
            tables = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite\\_%' ESCAPE '\\' "
                    "ORDER BY name"
                )
            ]
            self.assertEqual(
                tables,
                [
                    "attendance",
                    "children",
                    "groups",
                    "health_records",
                    "parents",
                    "vaccinations",
                ],
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0], 2
            )
        finally:
            conn.close()

    def test_source_unchanged_after_backup(self):
        before = sha256(self.db.db_file)
        self.assertTrue(self.db.backup_db(self.dest))
        self.assertEqual(sha256(self.db.db_file), before)
        # Source is still fully usable through the live connection.
        self.assertEqual(len(self.db.get_groups()), 2)

    def test_existing_destination_is_replaced(self):
        # A pre-existing, intentionally-corrupt destination must be replaced
        # atomically on success, not merged with or appended to.
        with open(self.dest, "wb") as fh:
            fh.write(b"NOT A DATABASE - previous backup content")

        self.assertTrue(self.db.backup_db(self.dest))
        self.assertEqual(sha256(self.dest), sha256(self.db.db_file))
        with open(self.dest, "rb") as fh:
            self.assertNotEqual(fh.read(4), b"NOT ")

    def test_pending_writes_are_flushed_before_backup(self):
        # Data committed only in memory must reach the backup.
        self.db.cursor.execute("INSERT INTO groups (name) VALUES ('Середнячки')")
        self.assertTrue(self.db.backup_db(self.dest))

        conn = sqlite3.connect(self.dest)
        try:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0], 3
            )
        finally:
            conn.close()

    def test_no_temp_residue_on_success(self):
        self.assertTrue(self.db.backup_db(self.dest))
        self.assertEqual(leftover_temp_files(self.dest_dir), [])

    def test_backup_into_nested_existing_subdir(self):
        sub = os.path.join(self.dest_dir, "nested")
        os.makedirs(sub)
        dest = os.path.join(sub, "backup.db")
        self.assertTrue(self.db.backup_db(dest))
        self.assertEqual(sha256(dest), sha256(self.db.db_file))


class TestBackupFailures(unittest.TestCase):
    def setUp(self):
        self.db, self.tmpdir = make_db()
        seed_groups(self.db, ["Малыши"])
        self.dest_dir = tempfile.mkdtemp(prefix="kgh_dest_")
        self.dest = os.path.join(self.dest_dir, "backup.db")
        with open(self.dest, "wb") as fh:
            fh.write(b"PREVIOUS BACKUP")

    def tearDown(self):
        dispose_db(self.db, self.tmpdir)
        shutil.rmtree(self.dest_dir, ignore_errors=True)

    def test_copy_failure_leaves_destination_intact(self):
        with mock.patch("shutil.copy2", side_effect=OSError("simulated disk full")):
            self.assertFalse(self.db.backup_db(self.dest))

        with open(self.dest, "rb") as fh:
            self.assertEqual(fh.read(), b"PREVIOUS BACKUP")

    def test_replace_failure_leaves_destination_intact(self):
        with mock.patch("os.replace", side_effect=OSError("simulated replace failure")):
            self.assertFalse(self.db.backup_db(self.dest))

        with open(self.dest, "rb") as fh:
            self.assertEqual(fh.read(), b"PREVIOUS BACKUP")

    def test_temp_files_cleaned_after_failure(self):
        with mock.patch("os.replace", side_effect=OSError("simulated replace failure")):
            self.assertFalse(self.db.backup_db(self.dest))

        self.assertEqual(leftover_temp_files(self.dest_dir), [])

    def test_source_unchanged_after_failure(self):
        before = sha256(self.db.db_file)
        with mock.patch("shutil.copy2", side_effect=OSError("simulated copy failure")):
            self.assertFalse(self.db.backup_db(self.dest))
        self.assertEqual(sha256(self.db.db_file), before)
        self.assertEqual(len(self.db.get_groups()), 1)

    def test_missing_destination_dir_is_rejected(self):
        nowhere = os.path.join(self.dest_dir, "does_not_exist", "backup.db")
        self.assertFalse(self.db.backup_db(nowhere))
        self.assertFalse(os.path.exists(nowhere))


class TestBackupSelfTarget(unittest.TestCase):
    """Backing the DB up onto itself must be rejected (Windows-safe paths)."""

    def setUp(self):
        self.db, self.tmpdir = make_db()

    def tearDown(self):
        dispose_db(self.db, self.tmpdir)

    def test_identical_absolute_path_rejected(self):
        self.assertFalse(self.db.backup_db(self.db.db_file))

    def test_relative_path_resolving_to_source_rejected(self):
        cwd = os.getcwd()
        try:
            os.chdir(self.tmpdir)
            name = os.path.basename(self.db.db_file)
            self.assertFalse(self.db.backup_db(name))
        finally:
            os.chdir(cwd)

    def test_self_backup_leaves_source_intact(self):
        before = sha256(self.db.db_file)
        self.assertFalse(self.db.backup_db(self.db.db_file))
        self.assertEqual(sha256(self.db.db_file), before)


if __name__ == "__main__":
    unittest.main()
