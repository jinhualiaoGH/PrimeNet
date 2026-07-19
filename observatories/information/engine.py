from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
import csv
import math

import numpy as np


@dataclass(frozen=True)
class InformationMetrics:
    state_labels: tuple[str, ...]
    transition_count: int
    active_source_states: int
    active_target_states: int
    source_entropy_bits: float
    target_entropy_bits: float
    joint_entropy_bits: float
    conditional_entropy_bits: float
    entropy_rate_bits: float
    mutual_information_bits: float
    normalized_mutual_information: float
    target_redundancy: float
    effective_target_alphabet: float
    predictability_fraction: float
    source_distribution: np.ndarray
    target_distribution: np.ndarray
    joint_distribution: np.ndarray
    conditional_probabilities: np.ndarray
    pointwise_mutual_information_bits: np.ndarray


def _entropy(probabilities: np.ndarray) -> float:
    positive = probabilities[probabilities > 0.0]
    if positive.size == 0:
        return 0.0
    return float(-np.sum(positive * np.log2(positive)))


def validate_transition_counts(counts: np.ndarray) -> np.ndarray:
    matrix = np.asarray(counts)
    if matrix.ndim != 2:
        raise ValueError("Transition counts must be a two-dimensional matrix.")
    if matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise ValueError("Transition counts must not be empty.")
    if matrix.shape[0] != matrix.shape[1]:
        raise ValueError("Transition counts must be square.")
    if not np.issubdtype(matrix.dtype, np.number):
        raise TypeError("Transition counts must be numeric.")
    matrix = matrix.astype(np.float64, copy=False)
    if not np.all(np.isfinite(matrix)):
        raise ValueError("Transition counts contain NaN or infinity.")
    if np.any(matrix < 0.0):
        raise ValueError("Transition counts must be non-negative.")
    if not np.allclose(matrix, np.rint(matrix), rtol=0.0, atol=1e-9):
        raise ValueError("Transition counts must be integer-valued.")
    if float(matrix.sum()) <= 0.0:
        raise ValueError("Transition counts must have positive total mass.")
    return matrix


def compute_information_metrics(
    transition_counts: np.ndarray,
    *,
    state_labels: Sequence[str] | None = None,
) -> InformationMetrics:
    counts = validate_transition_counts(transition_counts)
    n = counts.shape[0]
    if state_labels is None:
        labels = tuple(str(index) for index in range(n))
    else:
        labels = tuple(str(label) for label in state_labels)
        if len(labels) != n:
            raise ValueError("state_labels length must match matrix dimension.")
        if len(set(labels)) != len(labels):
            raise ValueError("state_labels must be unique.")

    total = float(counts.sum())
    joint = counts / total
    source = joint.sum(axis=1)
    target = joint.sum(axis=0)

    conditional = np.zeros_like(joint)
    active_rows = source > 0.0
    conditional[active_rows] = joint[active_rows] / source[active_rows, None]

    source_entropy = _entropy(source)
    target_entropy = _entropy(target)
    joint_entropy = _entropy(joint.ravel())
    conditional_entropy = float(
        sum(source[i] * _entropy(conditional[i]) for i in range(n) if source[i] > 0.0)
    )
    entropy_rate = conditional_entropy
    mutual_information = max(0.0, target_entropy - conditional_entropy)

    denom = math.sqrt(source_entropy * target_entropy)
    normalized_mi = mutual_information / denom if denom > 0.0 else 0.0

    active_target_count = int(np.count_nonzero(target))
    max_target_entropy = math.log2(active_target_count) if active_target_count > 1 else 0.0
    redundancy = (
        1.0 - target_entropy / max_target_entropy
        if max_target_entropy > 0.0
        else 0.0
    )
    predictability = (
        1.0 - conditional_entropy / target_entropy
        if target_entropy > 0.0
        else 0.0
    )

    pmi = np.zeros_like(joint)
    expected = source[:, None] * target[None, :]
    mask = (joint > 0.0) & (expected > 0.0)
    pmi[mask] = np.log2(joint[mask] / expected[mask])

    # Guard against insignificant floating-point excursions.
    normalized_mi = float(min(1.0, max(0.0, normalized_mi)))
    redundancy = float(min(1.0, max(0.0, redundancy)))
    predictability = float(min(1.0, max(0.0, predictability)))

    return InformationMetrics(
        state_labels=labels,
        transition_count=int(round(total)),
        active_source_states=int(np.count_nonzero(source)),
        active_target_states=active_target_count,
        source_entropy_bits=source_entropy,
        target_entropy_bits=target_entropy,
        joint_entropy_bits=joint_entropy,
        conditional_entropy_bits=conditional_entropy,
        entropy_rate_bits=entropy_rate,
        mutual_information_bits=mutual_information,
        normalized_mutual_information=normalized_mi,
        target_redundancy=redundancy,
        effective_target_alphabet=float(2.0**target_entropy),
        predictability_fraction=predictability,
        source_distribution=source,
        target_distribution=target,
        joint_distribution=joint,
        conditional_probabilities=conditional,
        pointwise_mutual_information_bits=pmi,
    )


def read_transition_counts_csv(path: Path | str) -> tuple[tuple[str, ...], np.ndarray]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Transition counts CSV not found: {source}")
    with source.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 2 or len(rows[0]) < 2:
        raise ValueError("Transition counts CSV is empty or malformed.")
    header_labels = tuple(cell.strip() for cell in rows[0][1:])
    row_labels: list[str] = []
    values: list[list[float]] = []
    for line_number, row in enumerate(rows[1:], start=2):
        if len(row) != len(header_labels) + 1:
            raise ValueError(f"CSV row {line_number} has the wrong number of columns.")
        row_labels.append(row[0].strip())
        try:
            values.append([float(value) for value in row[1:]])
        except ValueError as exc:
            raise ValueError(f"CSV row {line_number} contains a non-numeric count.") from exc
    if tuple(row_labels) != header_labels:
        raise ValueError("Transition count row and column labels must match in the same order.")
    return header_labels, validate_transition_counts(np.asarray(values, dtype=np.float64))
