from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
import csv
import math

import numpy as np


@dataclass(frozen=True)
class GeometryMetrics:
    state_labels: tuple[str, ...]
    active_mask: np.ndarray
    active_labels: tuple[str, ...]
    conditional_probabilities: np.ndarray
    jensen_shannon_distance: np.ndarray
    hellinger_distance: np.ndarray
    combined_distance: np.ndarray
    embedding_2d: np.ndarray
    embedding_3d: np.ndarray
    eigenvalues: np.ndarray
    cluster_assignments: np.ndarray
    nearest_neighbor_indices: np.ndarray
    nearest_neighbor_distances: np.ndarray
    active_state_count: int
    cluster_count: int
    mean_pairwise_distance: float
    max_pairwise_distance: float
    mean_nearest_neighbor_distance: float
    effective_dimension: float
    explained_variance_2d: float
    explained_variance_3d: float


def validate_transition_counts(counts: np.ndarray) -> np.ndarray:
    matrix = np.asarray(counts)
    if matrix.ndim != 2 or matrix.shape[0] == 0:
        raise ValueError("Transition counts must be a non-empty two-dimensional matrix.")
    if matrix.shape[0] != matrix.shape[1]:
        raise ValueError("Transition counts must be square.")
    if not np.issubdtype(matrix.dtype, np.number):
        raise TypeError("Transition counts must be numeric.")
    matrix = matrix.astype(np.float64, copy=False)
    if not np.all(np.isfinite(matrix)):
        raise ValueError("Transition counts contain NaN or infinity.")
    if np.any(matrix < 0.0):
        raise ValueError("Transition counts must be non-negative.")
    if float(matrix.sum()) <= 0.0:
        raise ValueError("Transition counts must have positive mass.")
    return matrix


def _entropy_rows(p: np.ndarray) -> np.ndarray:
    out = np.zeros(p.shape[0], dtype=np.float64)
    for i, row in enumerate(p):
        positive = row[row > 0.0]
        if positive.size:
            out[i] = -float(np.sum(positive * np.log2(positive)))
    return out


def _pairwise_js(p: np.ndarray) -> np.ndarray:
    n = p.shape[0]
    d = np.zeros((n, n), dtype=np.float64)
    hp = _entropy_rows(p)
    for i in range(n):
        for j in range(i + 1, n):
            m = 0.5 * (p[i] + p[j])
            positive = m[m > 0.0]
            hm = -float(np.sum(positive * np.log2(positive))) if positive.size else 0.0
            js = max(0.0, hm - 0.5 * hp[i] - 0.5 * hp[j])
            value = math.sqrt(js)
            d[i, j] = d[j, i] = value
    return d


def _pairwise_hellinger(p: np.ndarray) -> np.ndarray:
    roots = np.sqrt(p)
    diff = roots[:, None, :] - roots[None, :, :]
    return np.sqrt(np.sum(diff * diff, axis=2)) / math.sqrt(2.0)


def _classical_mds(distance: np.ndarray, dimensions: int) -> tuple[np.ndarray, np.ndarray]:
    n = distance.shape[0]
    if n == 1:
        return np.zeros((1, dimensions), dtype=np.float64), np.zeros(1)
    j = np.eye(n) - np.ones((n, n)) / n
    gram = -0.5 * j @ (distance * distance) @ j
    values, vectors = np.linalg.eigh(gram)
    order = np.argsort(values)[::-1]
    values = values[order]
    vectors = vectors[:, order]
    positive = np.clip(values, 0.0, None)
    k = min(dimensions, n)
    coords = vectors[:, :k] * np.sqrt(positive[:k])[None, :]
    if k < dimensions:
        coords = np.pad(coords, ((0, 0), (0, dimensions - k)))
    return coords, positive


def _average_linkage(distance: np.ndarray, cluster_count: int) -> np.ndarray:
    n = distance.shape[0]
    if not 1 <= cluster_count <= n:
        raise ValueError("cluster_count must be between 1 and the active state count.")
    clusters: list[list[int]] = [[i] for i in range(n)]
    while len(clusters) > cluster_count:
        best = None
        best_value = math.inf
        for a in range(len(clusters)):
            for b in range(a + 1, len(clusters)):
                value = float(distance[np.ix_(clusters[a], clusters[b])].mean())
                key = (value, min(clusters[a]), min(clusters[b]))
                if best is None or key < best_value_key:
                    best = (a, b)
                    best_value_key = key
                    best_value = value
        a, b = best
        merged = sorted(clusters[a] + clusters[b])
        clusters = [c for idx, c in enumerate(clusters) if idx not in (a, b)]
        clusters.append(merged)
        clusters.sort(key=lambda c: min(c))
    assignment = np.empty(n, dtype=np.int64)
    for cid, cluster in enumerate(clusters, start=1):
        assignment[cluster] = cid
    return assignment


def compute_geometry_metrics(
    transition_counts: np.ndarray,
    *,
    state_labels: Sequence[str] | None = None,
    cluster_count: int = 8,
    neighbor_count: int = 5,
    js_weight: float = 0.5,
) -> GeometryMetrics:
    counts = validate_transition_counts(transition_counts)
    n = counts.shape[0]
    labels = tuple(str(i) for i in range(n)) if state_labels is None else tuple(map(str, state_labels))
    if len(labels) != n or len(set(labels)) != n:
        raise ValueError("state_labels must be unique and match the matrix dimension.")
    if not 0.0 <= js_weight <= 1.0:
        raise ValueError("js_weight must be in [0, 1].")
    row_mass = counts.sum(axis=1)
    active_mask = row_mass > 0.0
    if not np.any(active_mask):
        raise ValueError("No active source states were found.")
    active_counts = counts[active_mask]
    conditional = active_counts / active_counts.sum(axis=1, keepdims=True)
    active_labels = tuple(label for label, active in zip(labels, active_mask) if active)
    js = _pairwise_js(conditional)
    hellinger = _pairwise_hellinger(conditional)
    combined = js_weight * js + (1.0 - js_weight) * hellinger
    np.fill_diagonal(combined, 0.0)
    emb3, eigenvalues = _classical_mds(combined, 3)
    emb2 = emb3[:, :2]
    active_n = len(active_labels)
    kclusters = min(cluster_count, active_n)
    assignments = _average_linkage(combined, kclusters)
    k_neighbors = min(neighbor_count, max(0, active_n - 1))
    if k_neighbors:
        neighbor_matrix = combined.copy()
        np.fill_diagonal(neighbor_matrix, np.inf)
        order = np.argsort(neighbor_matrix, axis=1)[:, :k_neighbors]
        ndist = np.take_along_axis(combined, order, axis=1)
    else:
        order = np.empty((active_n, 0), dtype=np.int64)
        ndist = np.empty((active_n, 0), dtype=np.float64)
    upper = combined[np.triu_indices(active_n, 1)]
    positive_eigs = eigenvalues[eigenvalues > 1e-14]
    effective_dimension = float((positive_eigs.sum() ** 2) / np.sum(positive_eigs ** 2)) if positive_eigs.size else 0.0
    total_eig = float(positive_eigs.sum())
    ev2 = float(eigenvalues[:2].sum() / total_eig) if total_eig else 0.0
    ev3 = float(eigenvalues[:3].sum() / total_eig) if total_eig else 0.0
    return GeometryMetrics(
        state_labels=labels,
        active_mask=active_mask,
        active_labels=active_labels,
        conditional_probabilities=conditional,
        jensen_shannon_distance=js,
        hellinger_distance=hellinger,
        combined_distance=combined,
        embedding_2d=emb2,
        embedding_3d=emb3,
        eigenvalues=eigenvalues,
        cluster_assignments=assignments,
        nearest_neighbor_indices=order,
        nearest_neighbor_distances=ndist,
        active_state_count=active_n,
        cluster_count=kclusters,
        mean_pairwise_distance=float(upper.mean()) if upper.size else 0.0,
        max_pairwise_distance=float(upper.max()) if upper.size else 0.0,
        mean_nearest_neighbor_distance=float(ndist[:, 0].mean()) if ndist.size else 0.0,
        effective_dimension=effective_dimension,
        explained_variance_2d=ev2,
        explained_variance_3d=ev3,
    )


def read_transition_counts_csv(path: Path | str) -> tuple[tuple[str, ...], np.ndarray]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Transition counts CSV not found: {source}")
    with source.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 2 or len(rows[0]) < 2:
        raise ValueError("Transition counts CSV is empty or malformed.")
    labels = tuple(cell.strip() for cell in rows[0][1:])
    row_labels, values = [], []
    for line, row in enumerate(rows[1:], start=2):
        if len(row) != len(labels) + 1:
            raise ValueError(f"CSV row {line} has the wrong number of columns.")
        row_labels.append(row[0].strip())
        try:
            values.append([float(value) for value in row[1:]])
        except ValueError as exc:
            raise ValueError(f"CSV row {line} contains a non-numeric count.") from exc
    if tuple(row_labels) != labels:
        raise ValueError("Transition count row and column labels must match.")
    return labels, validate_transition_counts(np.asarray(values, dtype=np.float64))
