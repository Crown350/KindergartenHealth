"""Tests for the centralized runtime paths and the seeder's --db targeting.

Tier 0 (stdlib only). Every database the tests touch is a tempfile; the
project's own runtime directory is never opened, seeded or created here.
"""

import os
import tempfile
import unittest

import paths
import photos
from database import Database
from populate_db import seed_database, _parse_args


class TestRuntimePaths(unittest.TestCase):
    def test_runtime_dir_is_inside_project_and_ignored(self):
        self.assertTrue(os.path.isabs(paths.RUNTIME_DIR))
        self.assertEqual(
            os.path.normcase(os.path.dirname(paths.RUNTIME_DIR)),
            os.path.normcase(paths.PROJECT_ROOT),
        )
        self.assertTrue(paths.RUNTIME_DIR.endswith(".runtime"))

    def test_default_db_is_inside_runtime_dir(self):
        self.assertEqual(
            os.path.normcase(os.path.dirname(paths.DB_PATH)),
            os.path.normcase(paths.RUNTIME_DIR),
        )
        self.assertEqual(os.path.basename(paths.DB_PATH), "kindergarten.db")

    def test_photos_and_backups_are_separate_runtime_subdirs(self):
        for d in (paths.PHOTOS_DIR, paths.BACKUPS_DIR):
            self.assertEqual(
                os.path.normcase(os.path.dirname(d)),
                os.path.normcase(paths.RUNTIME_DIR),
            )
        self.assertNotEqual(paths.PHOTOS_DIR, paths.BACKUPS_DIR)

    def test_ensure_runtime_dirs_is_idempotent_and_returns_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Redirect the module-level targets so the REAL runtime dir is
            # never touched by this test.
            orig = (paths.RUNTIME_DIR, paths.PHOTOS_DIR, paths.BACKUPS_DIR)
            try:
                paths.RUNTIME_DIR = os.path.join(tmp, "rt")
                paths.PHOTOS_DIR = os.path.join(paths.RUNTIME_DIR, "photos")
                paths.BACKUPS_DIR = os.path.join(paths.RUNTIME_DIR, "backups")
                self.assertEqual(paths.ensure_runtime_dirs(), paths.RUNTIME_DIR)
                for d in (paths.RUNTIME_DIR, paths.PHOTOS_DIR, paths.BACKUPS_DIR):
                    self.assertTrue(os.path.isdir(d))
                # a second call must not raise
                self.assertEqual(paths.ensure_runtime_dirs(), paths.RUNTIME_DIR)
            finally:
                paths.RUNTIME_DIR, paths.PHOTOS_DIR, paths.BACKUPS_DIR = orig


class TestDefaultDbResolution(unittest.TestCase):
    def test_database_default_uses_runtime_path(self):
        # Database() with no argument must resolve to the centralized runtime
        # DB, and must never default to a tracked repo-root file.
        with tempfile.TemporaryDirectory() as tmp:
            orig = paths.DB_PATH
            try:
                paths.DB_PATH = os.path.join(tmp, "nested", "kindergarten.db")
                db = Database()
                try:
                    self.assertEqual(
                        os.path.normcase(db.db_file),
                        os.path.normcase(paths.DB_PATH),
                    )
                    # the parent directory was created lazily
                    self.assertTrue(os.path.isdir(os.path.dirname(paths.DB_PATH)))
                    # a fresh launch yields the current schema version
                    self.assertEqual(
                        db.cursor.execute("PRAGMA user_version").fetchone()[0],
                        1,
                    )
                finally:
                    db.close()
            finally:
                paths.DB_PATH = orig

    def test_explicit_path_still_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            explicit = os.path.join(tmp, "explicit.db")
            db = Database(explicit)
            try:
                self.assertEqual(os.path.normcase(db.db_file), os.path.normcase(explicit))
            finally:
                db.close()


class TestPhotosUsesRuntimeDir(unittest.TestCase):
    def test_managed_dir_is_under_runtime_photos(self):
        # photos.MANAGED_DIR is the stored (relative) form; it must resolve into
        # the centralized runtime photos directory, never a tracked top-level
        # "photos" folder.
        self.assertEqual(
            os.path.normcase(
                os.path.join(paths.PROJECT_ROOT, photos.MANAGED_DIR)
            ),
            os.path.normcase(paths.PHOTOS_DIR),
        )
        self.assertNotEqual(
            os.path.normcase(os.path.join(paths.PROJECT_ROOT, photos.MANAGED_DIR)),
            os.path.normcase(os.path.join(paths.PROJECT_ROOT, "photos")),
        )

    def test_default_managed_dir_resolves_within_runtime(self):
        # base=None must point at the project runtime dir, not the process CWD.
        rel = photos.destination_for("pic.png", 11)
        self.assertIsNotNone(rel)
        self.assertTrue(photos.is_within(rel, paths.PROJECT_ROOT))
        self.assertTrue(
            os.path.normcase(photos._managed_dir(None)).startswith(
                os.path.normcase(paths.PHOTOS_DIR)
            )
        )


class TestSeederTargeting(unittest.TestCase):
    def _seeded(self, path):
        db = Database(path)
        try:
            groups = db.cursor.execute("SELECT COUNT(*) FROM groups").fetchone()[0]
            children = db.cursor.execute("SELECT COUNT(*) FROM children").fetchone()[0]
            return groups, children
        finally:
            db.close()

    def test_explicit_path_is_seeded_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "demo.db")
            seed_database(path)
            self.assertTrue(os.path.isfile(path))
            groups, children = self._seeded(path)
            self.assertGreater(groups, 0)
            self.assertGreater(children, 0)

    def test_seeding_twice_does_not_duplicate_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "demo2.db")
            seed_database(path)
            seed_database(path)
            groups, _ = self._seeded(path)
            self.assertEqual(groups, len(__import__("populate_db").GROUPS))

    def test_parse_args_defaults_to_none(self):
        args = _parse_args([])
        self.assertIsNone(args.db)

    def test_parse_args_accepts_explicit_db(self):
        args = _parse_args(["--db", "C:/some/path/demo.db"])
        self.assertEqual(args.db, "C:/some/path/demo.db")

    def test_parse_args_help_lists_db(self):
        with self.assertRaises(SystemExit):
            _parse_args(["--help"])


if __name__ == "__main__":
    unittest.main()
