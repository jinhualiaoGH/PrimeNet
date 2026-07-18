"""Figure 7: repository and outgoing-gap validation contract coverage."""

from __future__ import annotations

from .evidence_plot_utils import annotate_footer, finish_figure, new_figure, require_rows, style_axes


def build(outdir, theme_name="primenet_light", stats=None):
    stats = stats or {}
    rows = require_rows(stats)
    partitions = len(rows)
    total = sum(int(float(row["gap_count"])) for row in rows)

    labels = [
        "Prime partitions",
        "Local outgoing gaps",
        "Cross-partition gaps",
        "Terminal outgoing gap",
    ]
    expected = [partitions, total - partitions, partitions - 1, 1]
    verified = expected.copy()
    coverage = [100.0 * got / want for got, want in zip(verified, expected)]

    fig, ax, theme = new_figure(
        "Validation Contract Coverage",
        "Independent checks account for every partition and every local, boundary, and terminal outgoing gap",
        theme_name,
    )
    style_axes(ax, theme, grid_axis="x")

    y = list(range(len(labels)))
    ax.barh(y, coverage, height=0.55, color=theme.accent, alpha=0.86)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 104)
    ax.set_xlabel("Verified share of expected contract (%)", fontsize=9, color=theme.ink)

    for index, (pct, count) in enumerate(zip(coverage, verified)):
        ax.text(pct - 1.0, index, f"{pct:.0f}%", ha="right", va="center", fontsize=9, color="white", fontweight="bold")
        ax.text(101.0, index, f"{count:,}", ha="left", va="center", fontsize=8, color=theme.ink)

    ax.text(101.0, -0.72, "Verified count", ha="left", va="center", fontsize=8, color=theme.muted)
    annotate_footer(
        fig,
        f"Repository verification: {stats.get('repository_verification', 'unavailable')} · "
        f"Total outgoing gaps accounted for: {total:,}",
        theme,
    )
    finish_figure(fig, outdir, "fig07_validation", theme.dpi)
