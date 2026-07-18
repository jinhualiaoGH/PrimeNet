"""Figure 9: cumulative repository growth across the canonical numerical domain."""

from __future__ import annotations

from .evidence_plot_utils import annotate_footer, as_int, compact_formatter, finish_figure, new_figure, require_rows, style_axes


def build(outdir, theme_name="primenet_light", stats=None):
    stats = stats or {}
    rows = require_rows(stats)
    endpoints_t = [as_int(row, "range_end") / 1e12 for row in rows]
    cumulative_records = [as_int(row, "cumulative_gap_count") for row in rows]
    cumulative_gib = [count * 8 / (1024 ** 3) for count in cumulative_records]

    fig, ax, theme = new_figure(
        "Cumulative Repository Growth",
        "Measured growth of canonical prime records and their uint64 payload over the interval 1 ≤ n ≤ 3×10¹²",
        theme_name,
    )
    style_axes(ax, theme)

    line1 = ax.plot(endpoints_t, cumulative_records, linewidth=1.7, color=theme.accent, label="Cumulative prime records")[0]
    ax.fill_between(endpoints_t, cumulative_records, alpha=0.08, color=theme.accent)
    ax.set_xlabel("Numerical endpoint (trillion)", fontsize=9, color=theme.ink)
    ax.set_ylabel("Cumulative prime records", fontsize=9, color=theme.ink)
    ax.yaxis.set_major_formatter(compact_formatter())
    ax.set_xlim(0, 3.0)

    ax2 = ax.twinx()
    line2 = ax2.plot(endpoints_t, cumulative_gib, linewidth=1.3, linestyle="--", color=theme.accent2, label="Cumulative uint64 payload")[0]
    ax2.set_ylabel("Cumulative payload (GiB)", fontsize=9, color=theme.ink)
    ax2.tick_params(colors=theme.muted, labelsize=8)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_color(theme.container_edge)

    ax.legend([line1, line2], [line1.get_label(), line2.get_label()], loc="upper left", frameon=False, fontsize=8)
    annotate_footer(
        fig,
        f"Final measured repository size: {stats.get('repository_size_gb', 'unavailable')} GiB · "
        "Payload curve is derived from accepted uint64 record counts; file-system size includes NumPy headers.",
        theme,
    )
    finish_figure(fig, outdir, "fig09_growth", theme.dpi)
