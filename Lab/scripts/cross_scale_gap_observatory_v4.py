# cross_scale_gap_observatory_v4.py
# PrimeNet Cross-Scale Gap Observatory v4
# Quantitative distance geometry of normalized prime-gap distributions

from __future__ import annotations

import csv
import json
import math
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# =============================================================================
# Configuration
# =============================================================================

# =============================================================================
# Project paths
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
LAB_ROOT = SCRIPT_DIR.parent

DEFAULT_MANIFEST = LAB_ROOT / "config" / "normalized_manifest.csv"
DEFAULT_OUTPUT_DIR = LAB_ROOT / "outputs" / "cross_scale_v4"

EPS = 1e-15


# =============================================================================
# Utilities
# =============================================================================

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_float(x, default=np.nan) -> float:
    try:
        return float(x)
    except Exception:
        return default


def load_manifest(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")

    df = pd.read_csv(path)

    required = {"dataset_id", "source_path", "log_scale"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Manifest missing required columns: {sorted(missing)}")

    return df



def load_gap_distribution(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Distribution file not found: {path}")

    df = pd.read_csv(path)

    cols = {c.lower(): c for c in df.columns}

    gap_col = None
    count_col = None

    for name in ["gap", "raw_gap", "prime_gap"]:
        if name in cols:
            gap_col = cols[name]
            break

    for name in ["count", "frequency", "freq"]:
        if name in cols:
            count_col = cols[name]
            break

    if gap_col is None:
        raise ValueError(
            f"Could not identify gap column in {path}. "
            f"Columns found: {list(df.columns)}"
        )

    # Case 1: already aggregated distribution: gap,count
    if count_col is not None:
        out = df[[gap_col, count_col]].copy()
        out.columns = ["gap", "count"]

    # Case 2: raw event file: from_index,to_index,gap
    else:
        out = (
            df[gap_col]
            .dropna()
            .astype(float)
            .value_counts()
            .sort_index()
            .reset_index()
        )
        out.columns = ["gap", "count"]

    out["gap"] = out["gap"].astype(float)
    out["count"] = out["count"].astype(float)

    out = out[out["gap"] > 0]
    out = out[out["count"] > 0]
    out = out.sort_values("gap").reset_index(drop=True)

    total = out["count"].sum()
    if total <= 0:
        raise ValueError(f"No positive counts in {path}")

    out["probability"] = out["count"] / total
    return out

def normalize_distribution(df: pd.DataFrame, log_scale: float) -> pd.DataFrame:
    out = df.copy()
    out["normalized_gap"] = out["gap"] / log_scale
    return out[["gap", "normalized_gap", "count", "probability"]]


def build_common_grid(
    datasets: Dict[str, pd.DataFrame],
    bins: int = 400,
) -> np.ndarray:
    max_x = max(float(df["normalized_gap"].max()) for df in datasets.values())
    return np.linspace(0.0, max_x, bins + 1)


def histogram_on_grid(df: pd.DataFrame, grid: np.ndarray) -> np.ndarray:
    x = df["normalized_gap"].to_numpy()
    w = df["probability"].to_numpy()

    hist, _ = np.histogram(x, bins=grid, weights=w)
    s = hist.sum()

    if s <= 0:
        raise ValueError("Histogram mass vanished during gridding")

    return hist / s


# =============================================================================
# Distance metrics
# =============================================================================

def total_variation(p: np.ndarray, q: np.ndarray) -> float:
    return 0.5 * np.sum(np.abs(p - q))


def kl_divergence(p: np.ndarray, q: np.ndarray) -> float:
    p = np.asarray(p, dtype=float) + EPS
    q = np.asarray(q, dtype=float) + EPS
    return float(np.sum(p * np.log2(p / q)))


def jensen_shannon(p: np.ndarray, q: np.ndarray) -> float:
    m = 0.5 * (p + q)
    return 0.5 * kl_divergence(p, m) + 0.5 * kl_divergence(q, m)


def hellinger(p: np.ndarray, q: np.ndarray) -> float:
    return float(np.sqrt(0.5 * np.sum((np.sqrt(p) - np.sqrt(q)) ** 2)))


def wasserstein_1d(p: np.ndarray, q: np.ndarray, grid: np.ndarray) -> float:
    dx = np.diff(grid)
    cdf_p = np.cumsum(p)
    cdf_q = np.cumsum(q)
    return float(np.sum(np.abs(cdf_p - cdf_q) * dx))


def compute_pairwise(
    ids: List[str],
    histograms: Dict[str, np.ndarray],
    grid: np.ndarray,
) -> pd.DataFrame:
    rows = []

    for i, a in enumerate(ids):
        for j, b in enumerate(ids):
            p = histograms[a]
            q = histograms[b]

            rows.append(
                {
                    "dataset_a": a,
                    "dataset_b": b,
                    "jensen_shannon_bits": jensen_shannon(p, q),
                    "total_variation": total_variation(p, q),
                    "hellinger": hellinger(p, q),
                    "wasserstein_normalized_gap": wasserstein_1d(p, q, grid),
                }
            )

    return pd.DataFrame(rows)


def matrix_from_pairwise(pairwise: pd.DataFrame, metric: str, ids: List[str]) -> pd.DataFrame:
    mat = pairwise.pivot(index="dataset_a", columns="dataset_b", values=metric)
    return mat.loc[ids, ids]


# =============================================================================
# Plotting
# =============================================================================

def save_matrix_plot(matrix: pd.DataFrame, title: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(matrix.values)

    ax.set_title(title)
    ax.set_xticks(range(len(matrix.columns)))
    ax.set_yticks(range(len(matrix.index)))
    ax.set_xticklabels(matrix.columns, rotation=45, ha="right")
    ax.set_yticklabels(matrix.index)

    for i in range(len(matrix.index)):
        for j in range(len(matrix.columns)):
            ax.text(j, i, f"{matrix.values[i, j]:.3g}", ha="center", va="center")

    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def save_overlay_plot(
    datasets: Dict[str, pd.DataFrame],
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(9, 6))

    for dataset_id, df in datasets.items():
        ax.plot(
            df["normalized_gap"],
            df["probability"],
            marker="o",
            linewidth=1,
            markersize=2,
            label=dataset_id,
        )

    ax.set_title("Normalized Prime-Gap Distributions")
    ax.set_xlabel("normalized gap = raw gap / log(scale)")
    ax.set_ylabel("probability")
    ax.set_yscale("log")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


# =============================================================================
# Main observatory
# =============================================================================

def run_observatory(
    manifest_path: Path = DEFAULT_MANIFEST,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    bins: int = 400,
) -> None:
    t0 = time.perf_counter()

    ensure_dir(output_dir)
    ensure_dir(output_dir / "matrices")
    ensure_dir(output_dir / "figures")
    ensure_dir(output_dir / "normalized_distributions")

    print("=" * 72)
    print("PrimeNet Cross-Scale Gap Observatory v4")
    print("Distribution Distance Geometry")
    print("=" * 72)
    print(f"Manifest : {manifest_path}")
    print(f"Output   : {output_dir}")
    print("=" * 72)

    manifest = load_manifest(manifest_path)

    datasets: Dict[str, pd.DataFrame] = {}
    summaries = []

    for idx, row in manifest.iterrows():
        dataset_id = str(row["dataset_id"])
        data_path = Path(str(row["source_path"]))
        log_scale = safe_float(row["log_scale"])

        print(f"[{idx + 1}/{len(manifest)}] Loading {dataset_id}")

        raw = load_gap_distribution(data_path)
        norm = normalize_distribution(raw, log_scale)

        datasets[dataset_id] = norm

        norm.to_csv(
            output_dir / "normalized_distributions" / f"{dataset_id}_normalized.csv",
            index=False,
        )

        summaries.append(
            {
                "dataset_id": dataset_id,
                "source_path": str(data_path),
                "total_gaps": int(raw["count"].sum()),
                "distinct_raw_gaps": int(raw["gap"].nunique()),
                "min_raw_gap": float(raw["gap"].min()),
                "max_raw_gap": float(raw["gap"].max()),
                "log_scale": float(log_scale),
                "min_normalized_gap": float(norm["normalized_gap"].min()),
                "max_normalized_gap": float(norm["normalized_gap"].max()),
                "entropy_bits": float(
                    -np.sum(norm["probability"] * np.log2(norm["probability"]))
                ),
            }
        )

    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(output_dir / "dataset_summaries.csv", index=False)

    ids = list(datasets.keys())

    print("=" * 72)
    print("[Distance geometry] Building common normalized grid")
    grid = build_common_grid(datasets, bins=bins)

    histograms = {
        dataset_id: histogram_on_grid(df, grid)
        for dataset_id, df in datasets.items()
    }

    pairwise = compute_pairwise(ids, histograms, grid)
    pairwise.to_csv(output_dir / "pairwise_distances.csv", index=False)

    metrics = [
        "jensen_shannon_bits",
        "total_variation",
        "hellinger",
        "wasserstein_normalized_gap",
    ]

    for metric in metrics:
        matrix = matrix_from_pairwise(pairwise, metric, ids)
        matrix.to_csv(output_dir / "matrices" / f"{metric}_matrix.csv")

        save_matrix_plot(
            matrix,
            title=metric.replace("_", " ").title(),
            path=output_dir / "figures" / f"{metric}_matrix.png",
        )

    save_overlay_plot(
        datasets,
        output_dir / "figures" / "normalized_distribution_overlay.png",
    )

    runtime = time.perf_counter() - t0

    report = {
        "observatory": "PrimeNet Cross-Scale Gap Observatory v4",
        "description": "Quantitative distance geometry of normalized prime-gap distributions",
        "manifest": str(manifest_path),
        "output_dir": str(output_dir),
        "datasets_processed": len(ids),
        "bins": bins,
        "metrics": metrics,
        "runtime_seconds": runtime,
        "outputs": {
            "dataset_summaries": str(output_dir / "dataset_summaries.csv"),
            "pairwise_distances": str(output_dir / "pairwise_distances.csv"),
            "matrices": str(output_dir / "matrices"),
            "figures": str(output_dir / "figures"),
            "normalized_distributions": str(output_dir / "normalized_distributions"),
        },
    }

    with open(output_dir / "observatory_v4_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("=" * 72)
    print("Cross-scale distance geometry complete")
    print("=" * 72)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run_observatory()