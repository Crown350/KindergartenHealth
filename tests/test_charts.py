"""Tests for the statistics figure lifecycle (matplotlib, Agg backend, Tier 1).

The Agg backend is selected BEFORE importing charts so no display is needed.
Skips cleanly when matplotlib is not installed.
"""

import unittest

try:
    import matplotlib
    matplotlib.use("Agg")  # noqa: E402  (must precede pyplot import)
    import matplotlib.pyplot as plt  # noqa: E402
    import charts  # noqa: E402
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

COLORS = {"primary": "#4A90E2", "secondary": "#2ECC71", "accent": "#E67E22"}


def empty_stats():
    return {"children_per_group": [], "top_diagnoses": []}


def full_stats():
    return {
        "children_per_group": [("Младшая", 5), ("Старшая", 3)],
        "top_diagnoses": [("ОРВИ", 4), ("Грипп", 2)],
    }


@unittest.skipUnless(HAS_MPL, "matplotlib not installed")
class TestBuildStatsFigure(unittest.TestCase):
    def test_returns_figure_with_two_axes(self):
        fig = charts.build_stats_figure(empty_stats(), COLORS)
        try:
            self.assertEqual(len(fig.axes), 2)
        finally:
            charts.close_figure(fig)

    def test_bar_and_pie_populated(self):
        fig = charts.build_stats_figure(full_stats(), COLORS)
        try:
            self.assertTrue(fig.axes[0].patches)  # bars drawn
            self.assertTrue(fig.axes[1].patches)  # pie wedges drawn
        finally:
            charts.close_figure(fig)

    def test_empty_stats_still_builds_two_axes(self):
        fig = charts.build_stats_figure(empty_stats(), COLORS)
        try:
            self.assertEqual(len(fig.axes), 2)
            self.assertFalse(fig.axes[0].patches)
            self.assertFalse(fig.axes[1].patches)
        finally:
            charts.close_figure(fig)

    def test_titles_match_ui(self):
        fig = charts.build_stats_figure(full_stats(), COLORS)
        try:
            self.assertEqual(fig.axes[0].get_title(), "Дети по группам")
            self.assertEqual(fig.axes[1].get_title(), "Частые диагнозы")
        finally:
            charts.close_figure(fig)


@unittest.skipUnless(HAS_MPL, "matplotlib not installed")
class TestFigureLifecycle(unittest.TestCase):
    def open_count(self):
        return len(plt.get_fignums())

    def test_close_figure_reduces_open_count(self):
        before = self.open_count()
        fig = charts.build_stats_figure(full_stats(), COLORS)
        self.assertEqual(self.open_count(), before + 1)
        charts.close_figure(fig)
        self.assertEqual(self.open_count(), before)

    def test_close_none_and_double_close_safe(self):
        charts.close_figure(None)
        fig = charts.build_stats_figure(full_stats(), COLORS)
        charts.close_figure(fig)
        charts.close_figure(fig)  # must not raise

    def test_repeated_refresh_keeps_one_figure(self):
        before = self.open_count()
        fig = None
        for _ in range(5):
            fig = charts.refresh_stats_figure(fig, full_stats(), COLORS)
        self.assertEqual(self.open_count(), before + 1)  # exactly one, not five
        charts.close_figure(fig)
        self.assertEqual(self.open_count(), before)

    def test_refresh_closes_previous_figure(self):
        before = self.open_count()
        first = charts.build_stats_figure(full_stats(), COLORS)
        second = charts.refresh_stats_figure(first, full_stats(), COLORS)
        self.assertIsNot(first, second)
        self.assertEqual(self.open_count(), before + 1)
        charts.close_figure(second)
        self.assertEqual(self.open_count(), before)


if __name__ == "__main__":
    unittest.main()
