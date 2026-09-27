"""Batch A — the pure group-filter-choices helper.

``group_filter_choices(groups)`` builds the combo contents: the canonical
all-groups sentinel first, followed by the real group names. It is a pure
function living in database.py (the single owner of the sentinel) so it can
be unit-tested headlessly; main.py only wires it into the GUI combo.
"""

import unittest

from database import ALL_GROUPS, group_filter_choices
from tests.db_fixtures import make_db, dispose_db, seed_groups


class TestGroupFilterChoices(unittest.TestCase):
    def setUp(self):
        self.db, self.tmpdir = make_db()
        seed_groups(self.db, ["Малыши", "Старшая"])

    def tearDown(self):
        dispose_db(self.db, self.tmpdir)

    def test_all_groups_canonical_value(self):
        self.assertEqual(ALL_GROUPS, "Все")

    def test_choices_are_sentinel_then_group_names(self):
        choices = group_filter_choices(self.db.get_groups())
        self.assertEqual(choices[0], ALL_GROUPS)
        self.assertEqual(choices[1:], ["Малыши", "Старшая"])

    def test_sentinel_appear_exactly_once(self):
        choices = group_filter_choices(self.db.get_groups())
        self.assertEqual(choices.count(ALL_GROUPS), 1)

    def test_order_follows_get_groups(self):
        # get_groups() orders by name; choices must preserve that order.
        expected = [r["name"] for r in self.db.get_groups()]
        self.assertEqual(group_filter_choices(self.db.get_groups())[1:], expected)

    def test_empty_group_list_yields_only_sentinel(self):
        db, tmpdir = make_db()
        try:
            self.assertEqual(group_filter_choices(db.get_groups()), [ALL_GROUPS])
        finally:
            dispose_db(db, tmpdir)

    def test_helper_is_pure(self):
        rows = self.db.get_groups()
        first = group_filter_choices(rows)
        second = group_filter_choices(rows)
        # Repeated calls return equal results and never mutate the input.
        self.assertEqual(first, second)
        self.assertEqual([r["name"] for r in rows], ["Малыши", "Старшая"])


if __name__ == "__main__":
    unittest.main()
