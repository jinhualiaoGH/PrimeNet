from pathlib import Path
import numpy as np

from observatories.transition.engine import (
    canonical_states,
    compute_transitions,
    discover_gap_partitions,
)


def test_transition_census_preserves_cross_partition_boundary(tmp_path: Path) -> None:
    np.save(tmp_path / "gaps_1_10.npy", np.array([1, 2, 4], dtype=np.uint16))
    np.save(tmp_path / "gaps_11_20.npy", np.array([2, 6], dtype=np.uint16))
    parts = discover_gap_partitions(tmp_path)
    result = compute_transitions(parts, canonical_states(6), chunk_size=2)
    assert result.gaps_scanned == 5
    assert result.transitions_scanned == 4
    labels = list(result.states) + [None]
    i4 = labels.index(4)
    i2 = labels.index(2)
    assert result.counts[i4, i2] == 1  # cross-file transition
    assert int(result.counts.sum()) == 4
    assert np.isclose(result.stationary_distribution.sum(), 1.0)


def test_topology_rejects_missing_partition(tmp_path: Path) -> None:
    np.save(tmp_path / "gaps_1_10.npy", np.array([1, 2], dtype=np.uint16))
    np.save(tmp_path / "gaps_12_20.npy", np.array([4, 6], dtype=np.uint16))
    try:
        discover_gap_partitions(tmp_path)
    except ValueError as exc:
        assert "not contiguous" in str(exc)
    else:
        raise AssertionError("Expected topology failure")
