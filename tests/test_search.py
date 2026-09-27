"""Batch A — Cyrillic case-insensitive matching.

Covers confirmed MEDIUM defect #2: SQLite LIKE case-folds ASCII only, so
``get_children_summary`` name search and ``get_vaccine_reminders`` vaccine-name
matching were case-sensitive for Cyrillic (a lowercase query returned nothing).
"""

import unittest

from database import Database, ALL_GROUPS
from tests.db_fixtures import make_db, dispose_db, seed_groups, iso_days_ago


class TestCyrillicChildSearch(unittest.TestCase):
    def setUp(self):
        self.db, self.tmpdir = make_db()
        groups = seed_groups(self.db, ["Малыши"])
        self.group_id = groups["Малыши"]
        self.db.add_child("Иванов Иван", "2019-01-05", self.group_id)
        self.db.add_child("Петров Пётр", "2019-02-05", self.group_id)
        self.db.add_child("Сидорова Анна", "2019-03-05", self.group_id)

    def tearDown(self):
        dispose_db(self.db, self.tmpdir)

    @staticmethod
    def _names(rows):
        return sorted(r["full_name"] for r in rows)

    def _query(self, term):
        return self._names(self.db.get_children_summary(term, ALL_GROUPS))

    def test_case_variants_match_identically(self):
        expected = ["Иванов Иван"]
        for term in ("Иванов", "иванов", "ИВАНОВ", "ИвАнОв", "иВАНОВ"):
            with self.subTest(term=term):
                self.assertEqual(self._query(term), expected)

    def test_lowercase_cyrillic_finds_uppercase_stored_name(self):
        rows = self.db.get_children_summary("иванов", ALL_GROUPS)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["full_name"], "Иванов Иван")

    def test_uppercase_cyrillic_query(self):
        rows = self.db.get_children_summary("СИДОРОВА", ALL_GROUPS)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["full_name"], "Сидорова Анна")

    def test_yo_uppercase_casefolds_correctly(self):
        # 'Ё' must casefold to 'ё' (str.casefold, unlike ASCII-only LIKE).
        for term in ("Пётр", "пётр", "ПЁТР", "ПеТр"):
            with self.subTest(term=term):
                self.assertEqual(self._query(term), ["Петров Пётр"])

    def test_no_match_returns_empty(self):
        self.assertEqual(self._query("Несуществующий"), [])

    def test_empty_query_returns_all(self):
        self.assertEqual(
            len(self.db.get_children_summary("", ALL_GROUPS)), 3
        )

    def test_search_combined_with_group_filter(self):
        rows = self.db.get_children_summary("иванов", "Малыши")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["full_name"], "Иванов Иван")

    def test_search_does_not_leak_sql_injection(self):
        # User input must never be concatenated into SQL.
        self.assertEqual(self._query("Иванов' --"), [])
        self.assertEqual(self._query("%Иванов%"), [])


class TestCyrillicVaccineMatching(unittest.TestCase):
    """get_vaccine_reminders must match the vaccine name case-insensitively.

    Scope note (per audit): refusal / medical-exemption semantics and the
    primary-vs-revaccination rule are deliberately UNCHANGED — the reminders
    target 6-to-7-year-olds without a recent measles vaccination.
    """

    def setUp(self):
        self.db, self.tmpdir = make_db()
        groups = seed_groups(self.db, ["Подготовительная"])
        self.group_id = groups["Подготовительная"]
        # ~6.5 years old => inside the 6..7 candidate window.
        self.birth = iso_days_ago(365 * 6 + 180)
        self.recent = iso_days_ago(30)

    def tearDown(self):
        dispose_db(self.db, self.tmpdir)

    def _add_six_year_old(self, full_name):
        return self.db.add_child(full_name, self.birth, self.group_id)

    def _reminders_for(self, full_name):
        return [r for r in self.db.get_vaccine_reminders() if full_name in r]

    def test_no_vaccination_produces_reminder(self):
        self._add_six_year_old("Алексеев Алексей")
        self.assertEqual(len(self._reminders_for("Алексеев Алексей")), 1)

    def test_exact_case_measles_suppresses_reminder(self):
        cid = self._add_six_year_old("Борисов Борис")
        self.db.add_vaccination(cid, "Корь", self.recent, "Done")
        self.assertEqual(len(self._reminders_for("Борисов Борис")), 0)

    def test_lowercase_measles_suppresses_reminder(self):
        # Regression for the confirmed bug: 'корь' never matched LIKE '%Корь%'.
        cid = self._add_six_year_old("Волков Виктор")
        self.db.add_vaccination(cid, "корь", self.recent, "Done")
        self.assertEqual(len(self._reminders_for("Волков Виктор")), 0)

    def test_uppercase_measles_suppresses_reminder(self):
        cid = self._add_six_year_old("Громов Григорий")
        self.db.add_vaccination(cid, "КОРЬ", self.recent, "Done")
        self.assertEqual(len(self._reminders_for("Громов Григорий")), 0)

    def test_mixed_case_measles_suppresses_reminder(self):
        cid = self._add_six_year_old("Дмитриев Дмитрий")
        self.db.add_vaccination(cid, "кОрЬ", self.recent, "Done")
        self.assertEqual(len(self._reminders_for("Дмитриев Дмитрий")), 0)

    def test_unrelated_vaccine_does_not_suppress_reminder(self):
        cid = self._add_six_year_old("Егоров Егор")
        self.db.add_vaccination(cid, "Грипп", self.recent, "Done")
        self.assertEqual(len(self._reminders_for("Егоров Егор")), 1)

    def test_out_of_age_range_not_reminded(self):
        # 8 years old: outside the 6..7 window, so never a candidate.
        self.db.add_child("Жуков Жора", iso_days_ago(365 * 8), self.group_id)
        self.assertEqual(len(self._reminders_for("Жуков Жора")), 0)


if __name__ == "__main__":
    unittest.main()
