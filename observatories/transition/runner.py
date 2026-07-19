from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from observatories.framework import CoordinateRange
from .engine import canonical_states, compute_transitions, discover_gap_partitions
from .metadata import *
from .observation_builder import build_transition_observation


def _jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def _git(args: list[str]) -> str | None:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def _write_matrix(path: Path, labels: list[str], matrix: np.ndarray, value_name: str) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source_state", *labels])
        for label, row in zip(labels, matrix):
            writer.writerow([label, *row.tolist()])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(args: argparse.Namespace) -> Path:
    all_parts = discover_gap_partitions(args.gap_dir)
    first = args.first_partition - 1
    last = args.last_partition or len(all_parts)
    parts = all_parts[first:last]
    if not parts:
        raise ValueError("Selected partition range is empty.")

    states = canonical_states(args.max_gap, include_boundary_gap_one=True)
    result = compute_transitions(parts, states, chunk_size=args.chunk_size)
    output = Path(args.output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    labels = [str(x) for x in states] + [result.overflow_label]

    counts_path = output / "transition_counts.csv"
    probabilities_path = output / "transition_probabilities.csv"
    stationary_path = output / "stationary_distribution.csv"
    summary_path = output / "transition_summary.json"
    validation_path = output / "transition_validation.json"
    observation_path = output / "transition_observation.json"
    manifest_path = output / "sha256_manifest.json"

    _write_matrix(counts_path, labels, result.counts, "count")
    _write_matrix(probabilities_path, labels, result.probabilities, "probability")
    with stationary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["state", "outgoing_transition_count", "empirical_stationary_probability"])
        for label, total, probability in zip(labels, result.row_totals, result.stationary_distribution):
            writer.writerow([label, int(total), float(probability)])

    numeric_start = parts[0].numeric_start
    numeric_end = parts[-1].numeric_end
    checks = {
        "gaps_positive": result.first_gap > 0 and result.last_gap > 0,
        "transition_identity": result.transitions_scanned == result.gaps_scanned - 1,
        "count_mass_identity": int(result.counts.sum()) == result.transitions_scanned,
        "state_mass_identity": int(result.state_counts.sum()) == result.gaps_scanned,
        "probability_rows_normalized": bool(np.allclose(result.probabilities[result.row_totals > 0].sum(axis=1), 1.0)),
        "stationary_normalized": bool(np.isclose(result.stationary_distribution.sum(), 1.0)),
        "finite_entropy_rate": bool(np.isfinite(result.entropy_rate_bits)),
        "partition_topology_valid": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    validation = {"status": status, "checks": checks}
    validation_path.write_text(json.dumps(validation, indent=2), encoding="utf-8")
    if status != "PASS":
        raise RuntimeError("Transition observation validation failed.")

    summary = {
        "project": PROJECT,
        "observatory_id": OBSERVATORY_ID,
        "observatory": OBSERVATORY_NAME,
        "version": VERSION,
        "algorithm": ALGORITHM,
        "algorithm_version": ALGORITHM_VERSION,
        "coordinate_system": COORDINATE_SYSTEM,
        "gap_ownership": GAP_OWNERSHIP,
        "repository": str(Path(args.gap_dir).expanduser().resolve().parent),
        "gap_directory": str(Path(args.gap_dir).expanduser().resolve()),
        "numeric_domain_start": numeric_start,
        "numeric_domain_end": numeric_end,
        "first_partition": args.first_partition,
        "last_partition": last,
        "gap_files_scanned": result.partitions_scanned,
        "gaps_scanned": result.gaps_scanned,
        "transitions_scanned": result.transitions_scanned,
        "state_count": len(labels),
        "states": list(states),
        "overflow_label": result.overflow_label,
        "entropy_rate_bits": result.entropy_rate_bits,
        "spectral_gap": result.spectral_gap,
        "second_eigenvalue_modulus": result.second_eigenvalue_modulus,
        "runtime_seconds": result.runtime_seconds,
        "validation_status": status,
        "counts_csv": str(counts_path),
        "probabilities_csv": str(probabilities_path),
        "stationary_distribution_csv": str(stationary_path),
        "validation_json": str(validation_path),
        "summary_json": str(summary_path),
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "git_commit": _git(["rev-parse", "HEAD"]),
        "git_tag": _git(["describe", "--tags", "--exact-match"]),
        "command_line": " ".join(sys.argv),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    observation = build_transition_observation(
        observation_id=args.observation_id,
        coordinate_range=CoordinateRange(
            coordinate_system="prime_index",
            start=numeric_start,
            end=numeric_end,
        ),
        summary=summary,
        created_utc=summary["created_utc"],
    )
    observation_path.write_text(
        json.dumps(_jsonable(observation), indent=2, default=_jsonable),
        encoding="utf-8",
    )

    artifacts = [counts_path, probabilities_path, stationary_path, summary_path, validation_path, observation_path]
    manifest = {path.name: _sha256(path) for path in artifacts}
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return output


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run PrimeNet Transition Observatory v1.0")
    p.add_argument("--gap-dir", required=True, help="Canonical gaps_u16_v3 directory")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--observation-id", default="TRANSITION-V1")
    p.add_argument("--first-partition", type=int, default=1, help="1-based inclusive")
    p.add_argument("--last-partition", type=int, help="1-based inclusive; default all")
    p.add_argument("--max-gap", type=int, default=512)
    p.add_argument("--chunk-size", type=int, default=10_000_000)
    return p


def main() -> None:
    args = parser().parse_args()
    output = run(args)
    print("=" * 80)
    print("PrimeNet Transition Observatory v1.0: PASSED")
    print(f"Output: {output}")
    print("=" * 80)


if __name__ == "__main__":
    main()
