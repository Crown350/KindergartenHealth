"""Statistics figure construction with an explicit lifecycle.

The GUI must own AT MOST ONE statistics figure at a time: build it with
``build_stats_figure`` and release it with ``close_figure`` (or use
``refresh_stats_figure``, which does both). This keeps repeated visits to the
statistics view from accumulating matplotlib figures.

The backend is intentionally NOT forced here: the GUI needs the Tk backend
while tests select "Agg" before importing this module.
"""

import matplotlib.pyplot as plt


def build_stats_figure(stats, colors):
    """Build the dashboard statistics figure (children per group + top
    diagnoses) and return it. The construction is identical to the original
    inline implementation in main.py; only its ownership changed.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 4), facecolor="white")

    # Bar Chart
    if stats["children_per_group"]:
        groups = [x[0] for x in stats["children_per_group"]]
        counts = [x[1] for x in stats["children_per_group"]]
        ax1.bar(groups, counts, color=colors["primary"])
        ax1.set_title("Дети по группам")
        plt.setp(ax1.get_xticklabels(), rotation=30, ha="right")

    # Pie Chart
    if stats["top_diagnoses"]:
        diags = [x[0] for x in stats["top_diagnoses"]]
        d_counts = [x[1] for x in stats["top_diagnoses"]]
        ax2.pie(
            d_counts,
            labels=diags,
            autopct="%1.1f%%",
            colors=[
                colors["primary"],
                colors["secondary"],
                colors["accent"],
                "#9B59B6",
                "#34495E",
            ],
        )
        ax2.set_title("Частые диагнозы")

    return fig


def close_figure(fig):
    """Close a figure built by this module; safe on None and on a figure that
    was already closed."""
    if fig is None:
        return
    try:
        plt.close(fig)
    except Exception:
        # an already-closed/unknown figure must never break the view switch
        pass


def refresh_stats_figure(prev, stats, colors):
    """Close the previous figure (if any) and build a fresh one, so repeated
    refreshes never accumulate open figures."""
    close_figure(prev)
    return build_stats_figure(stats, colors)
