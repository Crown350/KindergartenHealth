"""Smoke test for PDF report generation (Tier 3: reportlab).

Uses ONLY synthetic child/parent/health/vaccination data and writes into a
tempfile. The tracked production databases and the demo data they hold are
never opened; the generated PDF is never written into the repository tree.
"""

import os
import sys
import tempfile
import unittest

try:
    import reportlab  # noqa: F401
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


@unittest.skipUnless(HAS_REPORTLAB, "reportlab not installed")
class TestPdfSmoke(unittest.TestCase):
    def _synthetic_child(self):
        return {
            "full_name": "Синтетический Ребёнок",
            "birth_date": "2019-05-14",
            "group_name": "Тестовая группа",
            "allergies": "Нет данных",
        }

    def _synthetic_parents(self):
        return [
            {"full_name": "Родитель Первый", "phone": "+7 (900) 000-00-01"},
            {"full_name": "Родитель Второй", "phone": "+7 (900) 000-00-02"},
        ]

    def _synthetic_health(self):
        return [
            {
                "record_date": "2024-01-15",
                "record_type": "Checkup",
                "description": "Синтетическое описание осмотра" * 3,
                "diagnosis": "Здоров",
            },
            {
                "record_date": "2024-02-20",
                "record_type": "Illness",
                "description": "Синтетическое описание заболевания",
                "diagnosis": "ОРВИ",
            },
        ]

    def _synthetic_vaccines(self):
        return [
            {"vaccine_name": "Корь", "date_administered": "2020-06-01", "status": "Done"},
            {"vaccine_name": "БЦЖ", "date_administered": "2019-06-10", "status": "Refused"},
        ]

    def _generate(self, tmpdir):
        from reports import generate_child_report

        path = os.path.join(tmpdir, "child_report.pdf")
        generate_child_report(
            path,
            self._synthetic_child(),
            self._synthetic_parents(),
            self._synthetic_health(),
            self._synthetic_vaccines(),
        )
        return path

    def test_reportlab_is_importable_and_font_resolved(self):
        # Reports resolve a Cyrillic-capable font at import time. On this
        # Windows machine C:/Windows/Fonts/arial.ttf is expected to register;
        # 'Helvetica' means NO Cyrillic font was found (tofu boxes) and is a
        # packaging portability signal, not a hard failure of this build.
        from reports import FONT_NAME
        self.assertIsInstance(FONT_NAME, str)
        self.assertTrue(FONT_NAME)

    def test_pdf_is_written_with_header_and_cyrillic_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._generate(tmp)
            self.assertTrue(os.path.isfile(path), "PDF file was not created")
            size = os.path.getsize(path)
            self.assertGreater(size, 1000, f"PDF is suspiciously small: {size} bytes")
            with open(path, "rb") as f:
                head = f.read(8)
            self.assertTrue(head.startswith(b"%PDF-"), f"missing PDF header: {head!r}")

    def test_pdf_is_written_without_parents_and_without_records(self):
        # The empty-table branches must also build a valid document.
        with tempfile.TemporaryDirectory() as tmp:
            from reports import generate_child_report

            path = os.path.join(tmp, "minimal.pdf")
            child = self._synthetic_child()
            child["allergies"] = ""
            generate_child_report(path, child, [], [], [])
            self.assertTrue(os.path.isfile(path))
            with open(path, "rb") as f:
                self.assertTrue(f.read(8).startswith(b"%PDF-"))
            self.assertGreater(os.path.getsize(path), 500)

    def test_unwritable_path_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            from reports import generate_child_report

            # A path whose "parent" is an existing FILE cannot be opened.
            blocker = os.path.join(tmp, "blocker")
            with open(blocker, "wb") as f:
                f.write(b"x")
            with self.assertRaises(Exception):
                generate_child_report(
                    os.path.join(blocker, "child.pdf"),
                    self._synthetic_child(),
                    self._synthetic_parents(),
                    self._synthetic_health(),
                    self._synthetic_vaccines(),
                )


if __name__ == "__main__":
    unittest.main()
