"""Tests for the managed photo lifecycle (stdlib only, Tier 0)."""

import os
import shutil
import tempfile
import unittest

import photos


class TestNormalizeExtension(unittest.TestCase):
    def test_png_stays_png(self):
        self.assertEqual(photos.normalize_extension(".png"), ".png")
        self.assertEqual(photos.normalize_extension("png"), ".png")
        self.assertEqual(photos.normalize_extension(".PNG"), ".png")

    def test_jpeg_normalizes_to_jpg(self):
        self.assertEqual(photos.normalize_extension(".jpg"), ".jpg")
        self.assertEqual(photos.normalize_extension(".jpeg"), ".jpg")
        self.assertEqual(photos.normalize_extension(".JPEG"), ".jpg")
        self.assertEqual(photos.normalize_extension("JPG"), ".jpg")

    def test_unsupported_rejected(self):
        for bad in ("", ".txt", ".exe", ".svg", ".html", ".db", "pngx", ".pdf"):
            self.assertIsNone(photos.normalize_extension(bad))


class TestDestination(unittest.TestCase):
    def test_filename_from_child_id_not_free_text(self):
        dest = photos.destination_for("C:/tmp/Иванов.png", 123)
        self.assertIsNotNone(dest)
        name = os.path.basename(dest)
        self.assertTrue(name.startswith("123_"), name)
        self.assertTrue(name.endswith(".png"), name)
        self.assertNotIn("Иванов", dest)

    def test_destination_inside_managed_dir(self):
        base = tempfile.mkdtemp()
        try:
            dest = photos.destination_for("photo.jpg", 7, base)
            self.assertIsNotNone(dest)
            self.assertTrue(photos.is_within(dest, base))
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_no_separators_in_destination_name(self):
        dest = photos.destination_for("photo.png", 5)
        name = os.path.basename(dest)
        self.assertNotIn("/", name)
        self.assertNotIn("\\", name)
        self.assertNotIn("..", name)

    def test_source_traversal_cannot_escape(self):
        base = tempfile.mkdtemp()
        try:
            dest = photos.destination_for("../../etc/evil.png", 9, base)
            self.assertTrue(photos.is_within(dest, base))
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_unsafe_child_id_rejected(self):
        with self.assertRaises(ValueError):
            photos.destination_for("photo.png", "../../..")

    def test_mixed_child_id_sanitized_and_contained(self):
        dest = photos.destination_for("photo.png", "1/2")
        self.assertTrue(photos.is_within(dest))
        self.assertIn("12", os.path.basename(dest))


class TestIsWithin(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_inside_accepted(self):
        self.assertTrue(photos.is_within(os.path.join(photos.MANAGED_DIR, "1.png"), self.base))
        self.assertTrue(
            photos.is_within(os.path.join(self.base, photos.MANAGED_DIR, "1.png"), self.base)
        )

    def test_outside_rejected(self):
        self.assertFalse(photos.is_within(os.path.join(self.base, "outside.png"), self.base))
        self.assertFalse(photos.is_within(os.path.join("..", "photos", "x.png"), self.base))
        self.assertFalse(photos.is_within("", self.base))
        self.assertFalse(photos.is_within(None, self.base))

    def test_traversal_rejected(self):
        evil = os.path.join(self.base, photos.MANAGED_DIR, "..", "outside.png")
        self.assertFalse(photos.is_within(evil, self.base))

    def test_managed_dir_itself_is_within(self):
        self.assertTrue(photos.is_within(os.path.join(self.base, photos.MANAGED_DIR), self.base))

    def test_different_drive_rejected_without_raising(self):
        if os.name != "nt":
            self.skipTest("drive letters are a Windows concept")
        root = os.path.splitdrive(os.path.abspath(self.base))[0].upper()
        other = "Z" if root != "Z" else "Y"
        self.assertFalse(photos.is_within(other + ":\\evil.png", self.base))


class TestImportAndDelete(unittest.TestCase):
    PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 32

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.managed = photos.ensure_managed_dir(self.base)
        self.source_png = os.path.join(self.base, "src.png")
        with open(self.source_png, "wb") as f:
            f.write(self.PNG_BYTES)
        self.source_txt = os.path.join(self.base, "src.txt")
        with open(self.source_txt, "w", encoding="utf-8") as f:
            f.write("not an image")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_import_copies_bytes_and_returns_managed_path(self):
        dest = photos.import_photo(self.source_png, 42, self.base)
        self.assertIsNotNone(dest)
        self.assertTrue(photos.is_within(dest, self.base))
        with open(os.path.join(self.base, dest), "rb") as f:
            self.assertEqual(f.read(), self.PNG_BYTES)

    def test_import_preserves_png_extension(self):
        dest = photos.import_photo(self.source_png, 42, self.base)
        self.assertEqual(os.path.splitext(dest)[1].lower(), ".png")

    def test_import_jpeg_extension_normalized(self):
        src = os.path.join(self.base, "pic.jpeg")
        shutil.copyfile(self.source_png, src)
        dest = photos.import_photo(src, 42, self.base)
        self.assertEqual(os.path.splitext(dest)[1].lower(), ".jpg")

    def test_import_rejects_unsupported_extension(self):
        self.assertIsNone(photos.import_photo(self.source_txt, 42, self.base))
        self.assertEqual(os.listdir(self.managed), [])

    def test_import_missing_source_is_none(self):
        missing = os.path.join(self.base, "nope.png")
        self.assertIsNone(photos.import_photo(missing, 42, self.base))

    def test_delete_removes_managed_photo(self):
        dest = photos.import_photo(self.source_png, 42, self.base)
        self.assertTrue(photos.delete_photo(dest, self.base))
        self.assertFalse(os.path.exists(os.path.join(self.base, dest)))

    def test_delete_refuses_outside_path(self):
        self.assertFalse(photos.delete_photo(self.source_png, self.base))
        self.assertTrue(os.path.exists(self.source_png))

    def test_delete_refuses_empty_and_directory(self):
        self.assertFalse(photos.delete_photo("", self.base))
        self.assertFalse(photos.delete_photo(None, self.base))
        self.assertFalse(photos.delete_photo(photos.MANAGED_DIR, self.base))
        self.assertTrue(os.path.isdir(self.managed))

    def test_delete_traversal_refused(self):
        outside = os.path.join(self.base, "outside.png")
        with open(outside, "wb") as f:
            f.write(b"x")
        evil = os.path.join(self.base, photos.MANAGED_DIR, "..", "outside.png")
        self.assertFalse(photos.delete_photo(evil, self.base))
        self.assertTrue(os.path.exists(outside))


class TestCommitPhotoUpdate(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.managed = photos.ensure_managed_dir(self.base)
        self.old = self._make_photo("old.png")
        self.fresh = self._make_photo("fresh.png")

    def _make_photo(self, name):
        path = os.path.join(self.managed, name)
        with open(path, "wb") as f:
            f.write(b"img")
        return os.path.join(photos.MANAGED_DIR, name)  # DB-style relative path

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def _abspath(self, rel):
        return os.path.join(self.base, rel)

    def test_success_releases_old_photo(self):
        committed = []

        def commit(path):
            committed.append(path)
            return True

        self.assertTrue(
            photos.commit_photo_update(self.old, self.fresh, self.fresh, commit, self.base)
        )
        self.assertEqual(committed, [self.fresh])
        self.assertFalse(os.path.exists(self._abspath(self.old)))
        self.assertTrue(os.path.exists(self._abspath(self.fresh)))

    def test_failure_keeps_old_and_removes_import(self):
        def commit(path):
            return False

        self.assertFalse(
            photos.commit_photo_update(self.old, self.fresh, self.fresh, commit, self.base)
        )
        self.assertTrue(os.path.exists(self._abspath(self.old)))
        self.assertFalse(os.path.exists(self._abspath(self.fresh)))

    def test_exception_keeps_old_and_removes_import(self):
        def commit(path):
            raise RuntimeError("DB down")

        self.assertFalse(
            photos.commit_photo_update(self.old, self.fresh, self.fresh, commit, self.base)
        )
        self.assertTrue(os.path.exists(self._abspath(self.old)))
        self.assertFalse(os.path.exists(self._abspath(self.fresh)))

    def test_unchanged_photo_commits_without_deleting(self):
        committed = []

        def commit(path):
            committed.append(path)
            return True

        self.assertTrue(
            photos.commit_photo_update(self.old, self.old, None, commit, self.base)
        )
        self.assertEqual(committed, [self.old])
        self.assertTrue(os.path.exists(self._abspath(self.old)))

    def test_failure_deletes_nothing_when_nothing_imported(self):
        def commit(path):
            raise RuntimeError("DB down")

        self.assertFalse(
            photos.commit_photo_update(self.old, self.old, None, commit, self.base)
        )
        self.assertTrue(os.path.exists(self._abspath(self.old)))

    def test_unmanaged_old_not_deleted_on_success(self):
        outside = os.path.join(self.base, "outside.png")
        with open(outside, "wb") as f:
            f.write(b"x")

        def commit(path):
            return True

        self.assertTrue(
            photos.commit_photo_update(outside, self.fresh, self.fresh, commit, self.base)
        )
        self.assertTrue(os.path.exists(outside))


if __name__ == "__main__":
    unittest.main()
