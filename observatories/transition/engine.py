from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Iterable, Sequence
import re

import numpy as np

_RANGE_RE = re.compile(r"^gaps_(\d+)_(\d+)\.npy$")


@dataclass(frozen=True)
class GapPartition:
    path: Path
    numeric_start: int
    numeric_end: int


@dataclass(frozen=True)
class TransitionResult:
    states: tuple[int, ...]
    overflow_label: str
    counts: np.ndarray
    probabilities: np.ndarray
    row_totals: np.ndarray
    state_counts: np.ndarray
    stationary_distribution: np.ndarray
    entropy_rate_bits: float
    spectral_gap: float | None
    second_eigenvalue_modulus: float | None
    gaps_scanned: int
    transitions_scanned: int
    partitions_scanned: int
    first_gap: int
    last_gap: int
    runtime_seconds: float


def discover_gap_partitions(directory: Path | str) -> list[GapPartition]:
    root = Path(directory).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Gap directory not found: {root}")
    parts: list[GapPartition] = []
    for path in root.glob("gaps_*.npy"):
        match = _RANGE_RE.match(path.name)
        if match:
            start, end = map(int, match.groups())
            parts.append(GapPartition(path, start, end))
    parts.sort(key=lambda p: (p.numeric_start, p.numeric_end))
    if not parts:
        raise FileNotFoundError(f"No canonical gaps_START_END.npy files found in {root}")
    for previous, current in zip(parts, parts[1:]):
        if current.numeric_start != previous.numeric_end + 1:
            raise ValueError(
                "Gap partition topology is not contiguous: "
                f"{previous.path.name} -> {current.path.name}"
            )
    return parts


def canonical_states(max_gap: int = 512, include_boundary_gap_one: bool = True) -> tuple[int, ...]:
    if max_gap < 2 or max_gap % 2:
        raise ValueError("max_gap must be an even integer >= 2.")
    values = list(range(2, max_gap + 1, 2))
    if include_boundary_gap_one:
        values.insert(0, 1)
    return tuple(values)


def _map_states(values: np.ndarray, states: np.ndarray) -> np.ndarray:
    positions = np.searchsorted(states, values)
    valid = positions < states.size
    exact = np.zeros(values.shape, dtype=bool)
    exact[valid] = states[positions[valid]] == values[valid]
    mapped = np.full(values.shape, states.size, dtype=np.int64)
    mapped[exact] = positions[exact]
    return mapped


def _spectral_summary(probabilities: np.ndarray, row_totals: np.ndarray) -> tuple[float | None, float | None]:
    active = row_totals > 0
    if int(active.sum()) < 2:
        return None, None
    matrix = probabilities[np.ix_(active, active)]
    # Renormalize after restricting to active states. Rows that lose all mass are omitted.
    sums = matrix.sum(axis=1)
    keep = sums > 0
    matrix = matrix[np.ix_(keep, keep)]
    if matrix.shape[0] < 2:
        return None, None
    matrix = matrix / matrix.sum(axis=1, keepdims=True)
    eigenvalues = np.linalg.eigvals(matrix)
    moduli = np.sort(np.abs(eigenvalues))[::-1]
    second = float(moduli[1])
    return float(max(0.0, 1.0 - second)), second


def compute_transitions(
    partitions: Sequence[GapPartition],
    states: Sequence[int],
    *,
    chunk_size: int = 10_000_000,
) -> TransitionResult:
    if chunk_size < 2:
        raise ValueError("chunk_size must be >= 2.")
    state_array = np.asarray(tuple(states), dtype=np.int64)
    if state_array.ndim != 1 or state_array.size == 0:
        raise ValueError("states must be a non-empty one-dimensional sequence.")
    if np.any(state_array <= 0) or np.any(np.diff(state_array) <= 0):
        raise ValueError("states must be strictly increasing positive integers.")

    size = state_array.size + 1  # final index is overflow/unlisted
    counts = np.zeros((size, size), dtype=np.uint64)
    state_counts = np.zeros(size, dtype=np.uint64)
    previous_gap: int | None = None
    first_gap: int | None = None
    last_gap: int | None = None
    gaps_scanned = 0
    transitions_scanned = 0
    started = perf_counter()

    for partition in partitions:
        gaps = np.load(partition.path, mmap_mode="r")
        if gaps.ndim != 1:
            raise ValueError(f"Gap array is not one-dimensional: {partition.path}")
        if gaps.size == 0:
            raise ValueError(f"Gap array is empty: {partition.path}")
        if gaps.dtype.kind not in "ui":
            raise ValueError(f"Gap array must be integer-valued: {partition.path}")

        for start in range(0, int(gaps.size), chunk_size):
            raw = np.asarray(gaps[start : start + chunk_size], dtype=np.int64)
            if np.any(raw <= 0):
                raise ValueError(f"Non-positive gap detected in {partition.path}")
            if first_gap is None:
                first_gap = int(raw[0])
            mapped = _map_states(raw, state_array)
            state_counts += np.bincount(mapped, minlength=size).astype(np.uint64)

            if previous_gap is not None:
                source = _map_states(np.asarray([previous_gap]), state_array)[0]
                counts[source, mapped[0]] += 1
                transitions_scanned += 1

            if mapped.size > 1:
                flat = mapped[:-1] * size + mapped[1:]
                counts += np.bincount(flat, minlength=size * size).reshape(size, size).astype(np.uint64)
                transitions_scanned += mapped.size - 1

            gaps_scanned += mapped.size
            previous_gap = int(raw[-1])
            last_gap = previous_gap

    row_totals = counts.sum(axis=1)
    probabilities = np.divide(
        counts,
        row_totals[:, None],
        out=np.zeros(counts.shape, dtype=np.float64),
        where=row_totals[:, None] != 0,
    )
    total_transitions = int(row_totals.sum())
    stationary = (
        row_totals.astype(np.float64) / total_transitions
        if total_transitions
        else np.zeros(size, dtype=np.float64)
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        row_entropy = -np.sum(
            np.where(probabilities > 0, probabilities * np.log2(probabilities), 0.0),
            axis=1,
        )
    entropy_rate = float(np.dot(stationary, row_entropy))
    spectral_gap, second = _spectral_summary(probabilities, row_totals)

    return TransitionResult(
        states=tuple(int(x) for x in state_array),
        overflow_label=f">{state_array[-1]} or unlisted",
        counts=counts,
        probabilities=probabilities,
        row_totals=row_totals,
        state_counts=state_counts,
        stationary_distribution=stationary,
        entropy_rate_bits=entropy_rate,
        spectral_gap=spectral_gap,
        second_eigenvalue_modulus=second,
        gaps_scanned=gaps_scanned,
        transitions_scanned=transitions_scanned,
        partitions_scanned=len(partitions),
        first_gap=int(first_gap),
        last_gap=int(last_gap),
        runtime_seconds=perf_counter() - started,
    )
