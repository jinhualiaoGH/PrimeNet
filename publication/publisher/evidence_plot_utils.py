"""Shared utilities for PrimeNet data-driven publication figures."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from .themes import get_theme


def new_figure(title: str, subtitle: str, theme_name: str = "primenet_light", *, width: float = 9.0, height: float = 5.8):
    theme = get_theme(theme_name)
    plt.rcParams["font.family"] = theme.font_family
    fig, ax = plt.subplots(figsize=(width, height))
    fig.patch.set_facecolor(theme.background)
    ax.set_facecolor(theme.background)
    fig.suptitle(title, fontsize=16, fontweight="bold", color=theme.ink, y=0.98)
    ax.set_title(subtitle, fontsize=9, color=theme.muted, pad=12)
    return fig, ax, theme


def finish_figure(fig, outdir, name: str, dpi: int = 260) -> None:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    fig.savefig(outdir / f"{name}.png", dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(outdir / f"{name}.svg", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def style_axes(ax, theme, *, grid_axis: str = "y") -> None:
    ax.grid(True, axis=grid_axis, linewidth=0.7, alpha=0.22)
    ax.set_axisbelow(True)
    ax.tick_params(colors=theme.muted, labelsize=8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(theme.container_edge)


def compact_number(value: float, _position=None) -> str:
    value = float(value)
    magnitude = abs(value)
    if magnitude >= 1e12:
        return f"{value / 1e12:.1f}T"
    if magnitude >= 1e9:
        return f"{value / 1e9:.1f}B"
    if magnitude >= 1e6:
        return f"{value / 1e6:.1f}M"
    if magnitude >= 1e3:
        return f"{value / 1e3:.1f}K"
    return f"{value:g}"


def compact_formatter() -> FuncFormatter:
    return FuncFormatter(compact_number)


def require_rows(stats: dict) -> list[dict]:
    rows = stats.get("_twin_census_rows") or []
    if not rows:
        source = stats.get("_twin_census_source", "unavailable")
        raise RuntimeError(f"Twin-prime partition evidence is unavailable: {source}")
    return rows


def annotate_footer(fig, text: str, theme) -> None:
    fig.text(0.5, 0.012, text, ha="center", va="bottom", fontsize=7.5, color=theme.muted)


def as_int(row: dict, key: str) -> int:
    return int(float(row[key]))


def as_float(row: dict, key: str) -> float:
    return float(row[key])
