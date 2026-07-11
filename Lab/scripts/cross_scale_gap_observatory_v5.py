# cross_scale_gap_observatory_v5.py
# PrimeNet Cross-Scale Gap Observatory v5
# Clustering and embedding geometry from v4 distance matrices

from __future__ import annotations

import json
import math
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

DEFAULT_V4_OUTPUT_DIR = LAB_ROOT / "outputs" / "cross_scale_v4"
DEFAULT_OUTPUT_DIR = LAB_ROOT / "outputs" / "cross_scale_v5"

PAIRWISE_FILE = DEFAULT_V4_OUTPUT_DIR / "pairwise_distances.csv"


# =============================================================================
# Utilities
# =============================================================================

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_pairwise(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"v4 pairwise distance file not found: {path}")

    df = pd.read_csv(path)

    required = {"dataset_a", "dataset_b"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Pairwise file missing required columns: {sorted(missing)}")

    return df


def available_metrics(pairwise: pd.DataFrame) -> List[str]:
    excluded = {"dataset_a", "dataset_b"}
    metrics = [
        c for c in pairwise.columns
        if c not in excluded and pd.api.types.is_numeric_dtype(pairwise[c])
    ]

    if not metrics:
        raise ValueError("No numeric distance metrics found in pairwise file")

    return metrics


def distance_matrix(pairwise: pd.DataFrame, metric: str) -> pd.DataFrame:
    ids = sorted(set(pairwise["dataset_a"]).union(set(pairwise["dataset_b"])))

    mat = pairwise.pivot(
        index="dataset_a",
        columns="dataset_b",
        values=metric,
    )

    mat = mat.loc[ids, ids]
    #mat = mat.astype(float)
    mat = mat.astype(float).copy()

    mat = mat.fillna(mat.T)
    #np.fill_diagonal(mat.values, 0.0)
    values = mat.to_numpy(dtype=float, copy=True)
    np.fill_diagonal(values, 0.0)
    mat.iloc[:, :] = values

    return mat


# =============================================================================
# Classical MDS
# =============================================================================

def classical_mds(D: np.ndarray, dim: int = 2) -> Tuple[np.ndarray, np.ndarray]:
    n = D.shape[0]

    if D.shape[0] != D.shape[1]:
        raise ValueError("Distance matrix must be square")

    D2 = D ** 2
    J = np.eye(n) - np.ones((n, n)) / n
    B = -0.5 * J @ D2 @ J

    eigvals, eigvecs = np.linalg.eigh(B)

    order = np.argsort(eigvals)[::-1]
    eigvals = eigvals[order]
    eigvecs = eigvecs[:, order]

    positive = np.maximum(eigvals[:dim], 0.0)
    coords = eigvecs[:, :dim] * np.sqrt(positive)

    return coords, eigvals


# =============================================================================
# Simple hierarchical clustering
# Average linkage, no scipy dependency
# =============================================================================

def average_linkage_clustering(
    D: np.ndarray,
    labels: List[str],
) -> Tuple[List[Dict], List[str]]:
    clusters = {
        i: {
            "members": [i],
            "label": labels[i],
            "height": 0.0,
        }
        for i in range(len(labels))
    }

    next_id = len(labels)
    merges = []

    def cluster_distance(a_members: List[int], b_members: List[int]) -> float:
        vals = [D[i, j] for i in a_members for j in b_members]
        return float(np.mean(vals))

    while len(clusters) > 1:
        keys = list(clusters.keys())

        best_pair = None
        best_dist = math.inf

        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                a = keys[i]
                b = keys[j]
                dist = cluster_distance(clusters[a]["members"], clusters[b]["members"])

                if dist < best_dist:
                    best_dist = dist
                    best_pair = (a, b)

        a, b = best_pair

        new_members = clusters[a]["members"] + clusters[b]["members"]

        merges.append(
            {
                "merge_id": len(merges) + 1,
                "cluster_a": clusters[a]["label"],
                "cluster_b": clusters[b]["label"],
                "distance": best_dist,
                "new_cluster": f"cluster_{next_id}",
                "members": [labels[i] for i in new_members],
            }
        )

        clusters[next_id] = {
            "members": new_members,
            "label": f"cluster_{next_id}",
            "height": best_dist,
        }

        del clusters[a]
        del clusters[b]
        next_id += 1

    final_members = list(clusters.values())[0]["members"]
    cluster_order = [labels[i] for i in final_members]

    return merges, cluster_order


# =============================================================================
# Plotting
# =============================================================================

def save_mds_plot(
    coords: np.ndarray,
    labels: List[str],
    metric: str,
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))

    ax.scatter(coords[:, 0], coords[:, 1])

    for i, label in enumerate(labels):
        ax.annotate(
            label,
            (coords[i, 0], coords[i, 1]),
            textcoords="offset points",
            xytext=(5, 5),
            ha="left",
        )

    ax.axhline(0, linewidth=0.8)
    ax.axvline(0, linewidth=0.8)

    ax.set_title(f"Cross-Scale MDS Embedding: {metric}")
    ax.set_xlabel("MDS dimension 1")
    ax.set_ylabel("MDS dimension 2")

    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def save_cluster_plot(
    merges: List[Dict],
    metric: str,
    output_path: Path,
) -> None:
    if not merges:
        return

    fig, ax = plt.subplots(figsize=(9, 5))

    x = np.arange(1, len(merges) + 1)
    y = [m["distance"] for m in merges]

    ax.plot(x, y, marker="o")

    for i, m in enumerate(merges):
        label = f'{m["cluster_a"]} + {m["cluster_b"]}'
        ax.annotate(
            label,
            (x[i], y[i]),
            textcoords="offset points",
            xytext=(5, 5),
            rotation=20,
            ha="left",
        )

    ax.set_title(f"Average-Linkage Merge Distances: {metric}")
    ax.set_xlabel("merge step")
    ax.set_ylabel("distance")

    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


# =============================================================================
# Main observatory
# =============================================================================

def run_observatory(
    pairwise_path: Path = PAIRWISE_FILE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> None:
    t0 = time.perf_counter()

    ensure_dir(output_dir)
    ensure_dir(output_dir / "figures")
    ensure_dir(output_dir / "matrices")
    ensure_dir(output_dir / "clusters")
    ensure_dir(output_dir / "embeddings")

    print("=" * 72)
    print("PrimeNet Cross-Scale Gap Observatory v5")
    print("Clustering and Embedding Geometry")
    print("=" * 72)
    print(f"Pairwise : {pairwise_path}")
    print(f"Output   : {output_dir}")
    print("=" * 72)

    pairwise = load_pairwise(pairwise_path)
    metrics = available_metrics(pairwise)

    all_embedding_rows = []
    all_cluster_rows = []
    summary = {}

    for metric in metrics:
        print(f"[Metric] {metric}")

        matrix = distance_matrix(pairwise, metric)
        labels = list(matrix.index)
        D = matrix.to_numpy(dtype=float)

        matrix.to_csv(output_dir / "matrices" / f"{metric}_matrix.csv")

        coords, eigvals = classical_mds(D, dim=2)

        explained = float(
            np.sum(np.maximum(eigvals[:2], 0.0))
            / max(np.sum(np.maximum(eigvals, 0.0)), 1e-15)
        )

        for i, label in enumerate(labels):
            all_embedding_rows.append(
                {
                    "metric": metric,
                    "dataset_id": label,
                    "mds_x": coords[i, 0],
                    "mds_y": coords[i, 1],
                    "positive_eigenvalue_explained_2d": explained,
                }
            )

        save_mds_plot(
            coords,
            labels,
            metric,
            output_dir / "figures" / f"mds_embedding_{metric}.png",
        )

        merges, cluster_order = average_linkage_clustering(D, labels)

        for m in merges:
            all_cluster_rows.append(
                {
                    "metric": metric,
                    "merge_id": m["merge_id"],
                    "cluster_a": m["cluster_a"],
                    "cluster_b": m["cluster_b"],
                    "distance": m["distance"],
                    "new_cluster": m["new_cluster"],
                    "members": ";".join(m["members"]),
                }
            )

        save_cluster_plot(
            merges,
            metric,
            output_dir / "figures" / f"hierarchical_cluster_{metric}.png",
        )

        summary[metric] = {
            "matrix_file": str(output_dir / "matrices" / f"{metric}_matrix.csv"),
            "mds_figure": str(output_dir / "figures" / f"mds_embedding_{metric}.png"),
            "cluster_figure": str(output_dir / "figures" / f"hierarchical_cluster_{metric}.png"),
            "cluster_order": cluster_order,
            "first_merge": merges[0] if merges else None,
            "positive_eigenvalue_explained_2d": explained,
            "eigenvalues": [float(x) for x in eigvals],
        }

    embedding_df = pd.DataFrame(all_embedding_rows)
    cluster_df = pd.DataFrame(all_cluster_rows)

    embedding_path = output_dir / "embeddings" / "distance_embedding_coordinates.csv"
    cluster_path = output_dir / "clusters" / "cluster_merges.csv"

    embedding_df.to_csv(embedding_path, index=False)
    cluster_df.to_csv(cluster_path, index=False)

    runtime = time.perf_counter() - t0

    report = {
        "observatory": "PrimeNet Cross-Scale Gap Observatory v5",
        "description": "Clustering and embedding geometry from v4 cross-scale distance matrices",
        "pairwise_input": str(pairwise_path),
        "output_dir": str(output_dir),
        "datasets": sorted(set(pairwise["dataset_a"]).union(set(pairwise["dataset_b"]))),
        "metrics_processed": metrics,
        "runtime_seconds": runtime,
        "outputs": {
            "embedding_coordinates": str(embedding_path),
            "cluster_merges": str(cluster_path),
            "matrices": str(output_dir / "matrices"),
            "figures": str(output_dir / "figures"),
            "report": str(output_dir / "observatory_v5_report.json"),
        },
        "metric_summaries": summary,
    }

    with open(output_dir / "observatory_v5_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("=" * 72)
    print("Cross-scale clustering and embedding complete")
    print("=" * 72)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run_observatory()