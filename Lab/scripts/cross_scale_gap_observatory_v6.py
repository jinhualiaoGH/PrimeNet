# cross_scale_gap_observatory_v6.py
# PrimeNet Cross-Scale Gap Observatory v6
# Cross-metric stability and consensus report from v4 + v5 outputs

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# =============================================================================
# Project paths
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
LAB_ROOT = SCRIPT_DIR.parent

V4_OUTPUT_DIR = LAB_ROOT / "outputs" / "cross_scale_v4"
V5_OUTPUT_DIR = LAB_ROOT / "outputs" / "cross_scale_v5"

PAIRWISE_FILE = V4_OUTPUT_DIR / "pairwise_distances.csv"
CLUSTER_FILE = V5_OUTPUT_DIR / "clusters" / "cluster_merges.csv"
EMBEDDING_FILE = V5_OUTPUT_DIR / "embeddings" / "distance_embedding_coordinates.csv"

DEFAULT_OUTPUT_DIR = LAB_ROOT / "outputs" / "cross_scale_v6"


# =============================================================================
# Utilities
# =============================================================================

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_required_csv(path: Path, name: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{name} not found: {path}")
    return pd.read_csv(path)


def numeric_metrics(pairwise: pd.DataFrame) -> List[str]:
    excluded = {"dataset_a", "dataset_b"}
    metrics = [
        c for c in pairwise.columns
        if c not in excluded and pd.api.types.is_numeric_dtype(pairwise[c])
    ]
    if not metrics:
        raise ValueError("No numeric metrics found in v4 pairwise distances")
    return metrics


def unique_dataset_ids(pairwise: pd.DataFrame) -> List[str]:
    ids = sorted(set(pairwise["dataset_a"]).union(set(pairwise["dataset_b"])))
    return ids


def distance_matrix(pairwise: pd.DataFrame, metric: str, ids: List[str]) -> pd.DataFrame:
    mat = pairwise.pivot(index="dataset_a", columns="dataset_b", values=metric)
    mat = mat.loc[ids, ids].astype(float).copy()
    mat = mat.fillna(mat.T)

    values = mat.to_numpy(dtype=float, copy=True)
    np.fill_diagonal(values, 0.0)
    mat.iloc[:, :] = values

    return mat


def upper_triangle_pairs(matrix: pd.DataFrame) -> pd.DataFrame:
    ids = list(matrix.index)
    rows = []

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            rows.append(
                {
                    "dataset_a": ids[i],
                    "dataset_b": ids[j],
                    "distance": float(matrix.iloc[i, j]),
                }
            )

    return pd.DataFrame(rows)


def rank_pairs(pair_df: pd.DataFrame) -> pd.DataFrame:
    out = pair_df.copy()
    out["pair"] = out["dataset_a"] + " | " + out["dataset_b"]
    out["rank"] = out["distance"].rank(method="min", ascending=True).astype(int)
    return out.sort_values(["rank", "distance"]).reset_index(drop=True)


def nearest_neighbor(matrix: pd.DataFrame) -> pd.DataFrame:
    ids = list(matrix.index)
    rows = []

    for dataset_id in ids:
        row = matrix.loc[dataset_id].copy()
        row.loc[dataset_id] = np.inf

        nn = row.idxmin()
        rows.append(
            {
                "dataset_id": dataset_id,
                "nearest_neighbor": nn,
                "nearest_distance": float(row.loc[nn]),
            }
        )

    return pd.DataFrame(rows)


# =============================================================================
# Stability analysis
# =============================================================================

def compute_pairwise_consensus(
    pairwise: pd.DataFrame,
    metrics: List[str],
    ids: List[str],
) -> pd.DataFrame:
    rows = []

    per_metric_ranked = {}

    for metric in metrics:
        matrix = distance_matrix(pairwise, metric, ids)
        ranked = rank_pairs(upper_triangle_pairs(matrix))
        ranked = ranked.rename(
            columns={
                "distance": f"{metric}_distance",
                "rank": f"{metric}_rank",
            }
        )
        per_metric_ranked[metric] = ranked[["pair", f"{metric}_distance", f"{metric}_rank"]]

    consensus = per_metric_ranked[metrics[0]]

    for metric in metrics[1:]:
        consensus = consensus.merge(per_metric_ranked[metric], on="pair", how="outer")

    rank_cols = [f"{m}_rank" for m in metrics]
    dist_cols = [f"{m}_distance" for m in metrics]

    consensus["mean_rank"] = consensus[rank_cols].mean(axis=1)
    consensus["std_rank"] = consensus[rank_cols].std(axis=1, ddof=0)
    consensus["rank_range"] = consensus[rank_cols].max(axis=1) - consensus[rank_cols].min(axis=1)
    consensus["mean_normalized_distance"] = consensus[dist_cols].apply(
        lambda row: np.mean([
            row[c] / max(consensus[c].max(), 1e-15)
            for c in dist_cols
        ]),
        axis=1,
    )

    consensus = consensus.sort_values(
        ["mean_rank", "std_rank", "mean_normalized_distance"]
    ).reset_index(drop=True)

    consensus["consensus_rank"] = np.arange(1, len(consensus) + 1)

    pair_split = consensus["pair"].str.split(" | ", regex=False, expand=True)
    consensus.insert(0, "dataset_a", pair_split[0])
    consensus.insert(1, "dataset_b", pair_split[1])

    return consensus


def compute_nearest_neighbor_consensus(
    pairwise: pd.DataFrame,
    metrics: List[str],
    ids: List[str],
) -> pd.DataFrame:
    rows = []

    for metric in metrics:
        matrix = distance_matrix(pairwise, metric, ids)
        nn = nearest_neighbor(matrix)

        for _, row in nn.iterrows():
            rows.append(
                {
                    "metric": metric,
                    "dataset_id": row["dataset_id"],
                    "nearest_neighbor": row["nearest_neighbor"],
                    "nearest_distance": row["nearest_distance"],
                }
            )

    nn_df = pd.DataFrame(rows)

    consensus_rows = []

    for dataset_id, group in nn_df.groupby("dataset_id"):
        counts = group["nearest_neighbor"].value_counts()
        best_neighbor = counts.index[0]
        support = int(counts.iloc[0])

        consensus_rows.append(
            {
                "dataset_id": dataset_id,
                "consensus_nearest_neighbor": best_neighbor,
                "support_count": support,
                "metric_count": len(metrics),
                "support_fraction": support / len(metrics),
                "all_neighbors": ";".join(group["nearest_neighbor"].tolist()),
            }
        )

    return pd.DataFrame(consensus_rows).sort_values(
        ["support_fraction", "dataset_id"],
        ascending=[False, True],
    )


def compute_first_merge_consensus(cluster_df: pd.DataFrame, metrics: List[str]) -> pd.DataFrame:
    rows = []

    for metric in metrics:
        g = cluster_df[cluster_df["metric"] == metric].sort_values("merge_id")
        if g.empty:
            continue

        first = g.iloc[0]
        pair = " | ".join(sorted([str(first["cluster_a"]), str(first["cluster_b"])]))

        rows.append(
            {
                "metric": metric,
                "first_merge_pair": pair,
                "first_merge_distance": float(first["distance"]),
                "members": str(first["members"]),
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    counts = df["first_merge_pair"].value_counts().rename_axis("first_merge_pair").reset_index(name="support_count")
    counts["metric_count"] = len(metrics)
    counts["support_fraction"] = counts["support_count"] / len(metrics)

    return counts.merge(df, on="first_merge_pair", how="left")


def compute_embedding_quality(embedding_df: pd.DataFrame) -> pd.DataFrame:
    if "positive_eigenvalue_explained_2d" not in embedding_df.columns:
        return pd.DataFrame()

    return (
        embedding_df[["metric", "positive_eigenvalue_explained_2d"]]
        .drop_duplicates()
        .sort_values("metric")
        .reset_index(drop=True)
    )


def stability_score(
    pair_consensus: pd.DataFrame,
    nn_consensus: pd.DataFrame,
    first_merge_consensus: pd.DataFrame,
    embedding_quality: pd.DataFrame,
) -> Dict:
    pair_rank_stability = float(
        1.0 - min(pair_consensus["std_rank"].mean() / max(len(pair_consensus), 1), 1.0)
    )

    nn_stability = float(nn_consensus["support_fraction"].mean())

    if not first_merge_consensus.empty:
        first_merge_stability = float(first_merge_consensus["support_fraction"].max())
    else:
        first_merge_stability = np.nan

    if not embedding_quality.empty:
        embedding_stability = float(embedding_quality["positive_eigenvalue_explained_2d"].mean())
    else:
        embedding_stability = np.nan

    components = [
        pair_rank_stability,
        nn_stability,
        first_merge_stability,
        embedding_stability,
    ]

    components = [x for x in components if not np.isnan(x)]

    overall = float(np.mean(components)) if components else np.nan

    return {
        "pair_rank_stability": pair_rank_stability,
        "nearest_neighbor_stability": nn_stability,
        "first_merge_stability": first_merge_stability,
        "embedding_2d_quality": embedding_stability,
        "overall_cross_metric_stability_score": overall,
    }


# =============================================================================
# Plotting
# =============================================================================

def save_consensus_rank_plot(pair_consensus: pd.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 6))

    x = np.arange(len(pair_consensus))
    y = pair_consensus["mean_rank"].to_numpy()
    err = pair_consensus["std_rank"].to_numpy()

    ax.errorbar(x, y, yerr=err, marker="o", linestyle="none")

    ax.set_xticks(x)
    ax.set_xticklabels(pair_consensus["pair"], rotation=45, ha="right")
    ax.set_title("Cross-Metric Pairwise Distance Consensus")
    ax.set_xlabel("dataset pair")
    ax.set_ylabel("mean rank across metrics")

    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def save_nearest_neighbor_plot(nn_consensus: pd.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))

    x = np.arange(len(nn_consensus))
    y = nn_consensus["support_fraction"].to_numpy()

    ax.bar(x, y)
    ax.set_xticks(x)
    ax.set_xticklabels(nn_consensus["dataset_id"], rotation=45, ha="right")

    ax.set_ylim(0, 1.05)
    ax.set_title("Nearest-Neighbor Stability Across Metrics")
    ax.set_xlabel("dataset")
    ax.set_ylabel("support fraction")

    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def save_embedding_quality_plot(embedding_quality: pd.DataFrame, output_path: Path) -> None:
    if embedding_quality.empty:
        return

    fig, ax = plt.subplots(figsize=(9, 5))

    x = np.arange(len(embedding_quality))
    y = embedding_quality["positive_eigenvalue_explained_2d"].to_numpy()

    ax.bar(x, y)
    ax.set_xticks(x)
    ax.set_xticklabels(embedding_quality["metric"], rotation=45, ha="right")

    ax.set_ylim(0, 1.05)
    ax.set_title("2D Embedding Quality by Metric")
    ax.set_xlabel("metric")
    ax.set_ylabel("positive eigenvalue explained in 2D")

    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


# =============================================================================
# Main observatory
# =============================================================================

def run_observatory(output_dir: Path = DEFAULT_OUTPUT_DIR) -> None:
    t0 = time.perf_counter()

    ensure_dir(output_dir)
    ensure_dir(output_dir / "figures")
    ensure_dir(output_dir / "tables")

    print("=" * 72)
    print("PrimeNet Cross-Scale Gap Observatory v6")
    print("Cross-Metric Stability and Consensus")
    print("=" * 72)
    print(f"v4 pairwise : {PAIRWISE_FILE}")
    print(f"v5 clusters : {CLUSTER_FILE}")
    print(f"v5 embedding: {EMBEDDING_FILE}")
    print(f"Output      : {output_dir}")
    print("=" * 72)

    pairwise = load_required_csv(PAIRWISE_FILE, "v4 pairwise distances")
    cluster_df = load_required_csv(CLUSTER_FILE, "v5 cluster merges")
    embedding_df = load_required_csv(EMBEDDING_FILE, "v5 embedding coordinates")

    metrics = numeric_metrics(pairwise)
    ids = unique_dataset_ids(pairwise)

    pair_consensus = compute_pairwise_consensus(pairwise, metrics, ids)
    nn_consensus = compute_nearest_neighbor_consensus(pairwise, metrics, ids)
    first_merge = compute_first_merge_consensus(cluster_df, metrics)
    embedding_quality = compute_embedding_quality(embedding_df)

    scores = stability_score(
        pair_consensus,
        nn_consensus,
        first_merge,
        embedding_quality,
    )

    pair_consensus_path = output_dir / "tables" / "pairwise_consensus_ranking.csv"
    nn_consensus_path = output_dir / "tables" / "nearest_neighbor_consensus.csv"
    first_merge_path = output_dir / "tables" / "first_merge_consensus.csv"
    embedding_quality_path = output_dir / "tables" / "embedding_quality.csv"
    score_path = output_dir / "tables" / "cross_metric_stability_scores.csv"

    pair_consensus.to_csv(pair_consensus_path, index=False)
    nn_consensus.to_csv(nn_consensus_path, index=False)
    first_merge.to_csv(first_merge_path, index=False)
    embedding_quality.to_csv(embedding_quality_path, index=False)
    pd.DataFrame([scores]).to_csv(score_path, index=False)

    save_consensus_rank_plot(
        pair_consensus,
        output_dir / "figures" / "pairwise_consensus_ranking.png",
    )
    save_nearest_neighbor_plot(
        nn_consensus,
        output_dir / "figures" / "nearest_neighbor_stability.png",
    )
    save_embedding_quality_plot(
        embedding_quality,
        output_dir / "figures" / "embedding_quality.png",
    )

    runtime = time.perf_counter() - t0

    report = {
        "observatory": "PrimeNet Cross-Scale Gap Observatory v6",
        "description": "Cross-metric stability and consensus analysis from v4 distances and v5 geometry",
        "inputs": {
            "pairwise_distances": str(PAIRWISE_FILE),
            "cluster_merges": str(CLUSTER_FILE),
            "embedding_coordinates": str(EMBEDDING_FILE),
        },
        "output_dir": str(output_dir),
        "datasets": ids,
        "metrics": metrics,
        "runtime_seconds": runtime,
        "outputs": {
            "pairwise_consensus_ranking": str(pair_consensus_path),
            "nearest_neighbor_consensus": str(nn_consensus_path),
            "first_merge_consensus": str(first_merge_path),
            "embedding_quality": str(embedding_quality_path),
            "cross_metric_stability_scores": str(score_path),
            "figures": str(output_dir / "figures"),
            "report": str(output_dir / "observatory_v6_report.json"),
        },
        "stability_scores": scores,
        "top_consensus_pair": (
            pair_consensus.iloc[0][["dataset_a", "dataset_b", "mean_rank", "std_rank"]].to_dict()
            if not pair_consensus.empty else None
        ),
        "first_merge_consensus": (
            first_merge.iloc[0].to_dict()
            if not first_merge.empty else None
        ),
    }

    with open(output_dir / "observatory_v6_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("=" * 72)
    print("Cross-metric stability and consensus complete")
    print("=" * 72)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run_observatory()