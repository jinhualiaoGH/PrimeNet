"""Figure 8: measured twin-prime census runtime across canonical partitions."""

from __future__ import annotations

import statistics

from .evidence_plot_utils import annotate_footer, as_float, as_int, finish_figure, new_figure, require_rows, style_axes


def build(outdir, theme_name="primenet_light", stats=None):
    stats = stats or {}
    rows = require_rows(stats)
    partitions = [as_int(row, "partition") for row in rows]
    runtimes = [as_float(row, "runtime_sec") for row in rows]
    steady = runtimes[10:]
    median = statistics.median(steady)
    p95 = sorted(steady)[round(0.95 * (len(steady) - 1))]

    fig, ax, theme = new_figure(
        "Twin-Prime Census Runtime by Partition",
        "Measured execution time for the complete 3T census; partitions 11–300 define the conservative steady state",
        theme_name,
    )
    style_axes(ax, theme)

    ax.axvspan(11, 300, alpha=0.06, color=theme.accent, label="Conservative steady state")
    ax.plot(partitions, runtimes, linewidth=1.1, color=theme.accent, label="Partition runtime")
    ax.scatter(partitions, runtimes, s=8, alpha=0.45, color=theme.accent)
    ax.axhline(median, linewidth=1.0, linestyle="--", color=theme.accent2, label=f"Steady median {median:.3f} s")
    ax.axhline(p95, linewidth=0.9, linestyle=":", color=theme.muted, label=f"Steady p95 {p95:.3f} s")
    ax.set_xlim(1, 300)
    ax.set_xlabel("Canonical partition", fontsize=9, color=theme.ink)
    ax.set_ylabel("Runtime (seconds)", fontsize=9, color=theme.ink)
    ax.legend(loc="upper right", frameon=False, fontsize=8)

    annotate_footer(
        fig,
        f"Steady-state CV: {stats.get('steady_runtime_cv_percent', 'unavailable')} · "
        f"Sustained throughput: {stats.get('steady_gaps_per_sec', 'unavailable')} gaps/s · "
        f"Runtime accounted: {stats.get('twin_runtime_accounted_percent', 'unavailable')}",
        theme,
    )
    finish_figure(fig, outdir, "fig08_performance", theme.dpi)
