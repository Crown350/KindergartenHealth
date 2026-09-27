"""Batch A — canonical all-groups behaviour of Database.get_children_summary.

Covers confirmed CRITICAL defect #1a (sentinel mismatch): the GUI default was
"Все" while the data layer only special-cased the English sentinel "All",
so the child list was permanently empty.
"""

import unittest

from database import Database, ALL_GROUPS
from tests.db_fixtures import make_db, dispose_db, seed_groups


class TestGroupFilter(unittest.TestCase):
    def setUp(self):
        self.db, self.tmpdir = make_db()
        groups = seed_groups(self.db, ["Малыши", "Старшая"])
        self.malyshi = groups["Малыши"]
        self.starshaya = groups["Старшая"]
        self.db.add_child("Иванов Иван", "2019-01-05", self.malyshi)
        self.db.add_child("Петров Пётр", "2019-02-05", self.malyshi)
        self.db.add_child("Сидоров Сидор", "2019-03-05", self.malyshi)
        self.db.add_child("Кузнецов Кузьма", "2018-01-05", self.starshaya)
        self.db.add_child("Смирнов Сергей", "2018-02-05", self.starshaya)
        self.total = 5

    def tearDown(self):
        dispose_db(self.db, self.tmpdir)

    @staticmethod
    def _names(rows):
        return sorted(r["full_name"] for r in rows)

    # --- canonical sentinel: None / "" / ALL_GROUPS / legacy "All" ---------

    def test_none_is_unfiltered(self):
        rows = self.db.get_children_summary("", None)
        self.assertEqual(len(rows), self.total)

    def test_empty_string_is_unfiltered(self):
        rows = self.db.get_children_summary("", "")
        self.assertEqual(len(rows), self.total)

    def test_all_groups_sentinel_matches_unfiltered(self):
        unfiltered = self.db.get_children_summary("", None)
        by_sentinel = self.db.get_children_summary("", ALL_GROUPS)
        self.assertEqual(len(unfiltered), self.total)
        self.assertEqual(len(by_sentinel), self.total)
        self.assertEqual(self._names(unfiltered), self._names(by_sentinel))

    def test_legacy_english_all_sentinel_still_unfiltered(self):
        # "All" is accepted for backwards compatibility with any saved state.
        rows = self.db.get_children_summary("", "All")
        self.assertEqual(len(rows), self.total)

    def test_default_group_filter_is_unfiltered(self):
        # No group_filter argument at all must return every child.
        rows = self.db.get_children_summary("")
        self.assertEqual(len(rows), self.total)

    # --- real filters ------------------------------------------------------

    def test_real_group_filter_returns_exact_subset(self):
        rows = self.db.get_children_summary("", "Малыши")
        self.assertEqual(len(rows), 3)
        self.assertEqual(
            self._names(rows),
            ["Иванов Иван", "Петров Пётр", "Сидоров Сидор"],
        )

    def test_other_real_group_filter_returns_exact_subset(self):
        rows = self.db.get_children_summary("", "Старшая")
        self.assertEqual(len(rows), 2)
        self.assertEqual(self._names(rows), ["Кузнецов Кузьма", "Смирнов Сергей"])

    def test_unknown_group_returns_zero_rows(self):
        rows = self.db.get_children_summary("", "Несуществующая группа")
        self.assertEqual(len(rows), 0)

    def test_sentinel_is_never_treated_as_a_real_group_name(self):
        # Even if no group is literally named "Все", the sentinel filters
        # nothing (regression guard for the original empty-list bug).
        rows = self.db.get_children_summary("", ALL_GROUPS)
        self.assertEqual(len(rows), self.total)

    # --- DB state is untouched by filtering --------------------------------

    def test_db_state_unchanged_after_filtering(self):
        before = len(self.db.get_children_summary("", None))
        self.db.get_children_summary("", "Малыши")
        self.db.get_children_summary("", "Старшая")
        self.db.get_children_summary("", "Несуществующая группа")
        self.db.get_children_summary("", ALL_GROUPS)
        after = len(self.db.get_children_summary("", None))
        self.assertEqual(before, after)

        self.db.cursor.execute("SELECT COUNT(*) FROM children")
        self.assertEqual(self.db.cursor.fetchone()[0], self.total)
        self.db.cursor.execute("SELECT COUNT(*) FROM groups")
        self.assertEqual(self.db.cursor.fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main()
