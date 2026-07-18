"""Figure 6: measured partition-scale profile of the canonical repository."""

from __future__ import annotations

from .evidence_plot_utils import (
    annotate_footer,
    as_int,
    compact_formatter,
    finish_figure,
    new_figure,
    require_rows,
    style_axes,
)


def build(outdir, theme_name="primenet_light", stats=None):
    stats = stats or {}
    rows = require_rows(stats)
    partitions = [as_int(row, "partition") for row in rows]
    prime_counts = [as_int(row, "gap_count") for row in rows]
    partition_gib = [count * 8 / (1024 ** 3) for count in prime_counts]

    fig, ax, theme = new_figure(
        "Canonical Repository Scale by Partition",
        "Measured record count and uint64 storage footprint across 300 canonical 10B partitions",
        theme_name,
    )
    style_axes(ax, theme)

    line1 = ax.plot(partitions, prime_counts, linewidth=1.5, label="Prime records", color=theme.accent)[0]
    ax.fill_between(partitions, prime_counts, alpha=0.10, color=theme.accent)
    ax.set_xlabel("Canonical partition", fontsize=9, color=theme.ink)
    ax.set_ylabel("Prime records per partition", fontsize=9, color=theme.ink)
    ax.yaxis.set_major_formatter(compact_formatter())
    ax.set_xlim(partitions[0], partitions[-1])

    ax2 = ax.twinx()
    line2 = ax2.plot(partitions, partition_gib, linewidth=1.2, linestyle="--", label="Derived uint64 size", color=theme.accent2)[0]
    ax2.set_ylabel("Partition payload (GiB)", fontsize=9, color=theme.ink)
    ax2.tick_params(colors=theme.muted, labelsize=8)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_color(theme.container_edge)

    ax.legend([line1, line2], [line1.get_label(), line2.get_label()], loc="upper right", frameon=False, fontsize=8)
    annotate_footer(
        fig,
        f"Source: {stats.get('_twin_census_source', 'accepted twin-prime census CSV')} · "
        f"Total records: {stats.get('verified_prime_numbers', 'unavailable')} · "
        f"Repository interval: {stats.get('repository_interval', 'unavailable')}",
        theme,
    )
    finish_figure(fig, outdir, "fig06_repository_scale", theme.dpi)
