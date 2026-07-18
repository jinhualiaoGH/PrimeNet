"""Figure 10: twin-prime observational density across canonical partitions."""

from __future__ import annotations

from .evidence_plot_utils import annotate_footer, as_float, as_int, finish_figure, new_figure, require_rows, style_axes


def build(outdir, theme_name="primenet_light", stats=None):
    stats = stats or {}
    rows = require_rows(stats)
    partitions = [as_int(row, "partition") for row in rows]
    local_density = [100.0 * as_float(row, "twin_density") for row in rows]
    cumulative_density = [100.0 * as_float(row, "cumulative_twin_density") for row in rows]
    global_density = 100.0 * as_float(rows[-1], "cumulative_twin_density")

    fig, ax, theme = new_figure(
        "Twin-Prime Observatory Output",
        "Partition and cumulative twin-event density from a complete scan of the accepted outgoing-gap repository",
        theme_name,
    )
    style_axes(ax, theme)

    ax.plot(partitions, local_density, linewidth=0.9, alpha=0.55, color=theme.accent, label="Partition density")
    ax.plot(partitions, cumulative_density, linewidth=1.8, color=theme.accent2, label="Cumulative density")
    ax.axhline(global_density, linewidth=0.9, linestyle="--", color=theme.muted, label=f"Global density {global_density:.4f}%")
    ax.set_xlim(1, 300)
    ax.set_xlabel("Canonical partition", fontsize=9, color=theme.ink)
    ax.set_ylabel("Twin events per outgoing gap (%)", fontsize=9, color=theme.ink)
    ax.legend(loc="upper right", frameon=False, fontsize=8)

    annotate_footer(
        fig,
        f"Complete finite-domain observation: {stats.get('twin_total_gaps', 'unavailable')} gaps · "
        f"{stats.get('twin_total_events', 'unavailable')} twin events · event definition g(i) = 2.",
        theme,
    )
    finish_figure(fig, outdir, "fig10_observatory", theme.dpi)
