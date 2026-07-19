from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from observatories.framework import CoordinateRange
from .engine import compute_information_metrics, read_transition_counts_csv
from .metadata import *
from .observation_builder import build_transition_metrics_information_observation


def _jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_distribution(path: Path, labels: tuple[str, ...], source: np.ndarray, target: np.ndarray) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["state", "source_probability", "target_probability"])
        for label, p_source, p_target in zip(labels, source, target):
            writer.writerow([label, float(p_source), float(p_target)])


def _write_matrix(path: Path, labels: tuple[str, ...], matrix: np.ndarray) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source_state", *labels])
        for label, row in zip(labels, matrix):
            writer.writerow([label, *[float(value) for value in row]])


def run(args: argparse.Namespace) -> Path:
    started = time.perf_counter()
    input_dir = Path(args.transition_output_dir).expanduser().resolve()
    counts_path = input_dir / "transition_counts.csv"
    transition_summary_path = input_dir / "transition_summary.json"
    if not transition_summary_path.is_file():
        raise FileNotFoundError(f"Transition summary not found: {transition_summary_path}")
    transition_summary = json.loads(transition_summary_path.read_text(encoding="utf-8"))
    if transition_summary.get("validation_status") != "PASS":
        raise ValueError("Source Transition observation is not validated.")

    labels, counts = read_transition_counts_csv(counts_path)
    metrics = compute_information_metrics(counts, state_labels=labels)
    output = Path(args.output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    distribution_path = output / "information_distributions.csv"
    pmi_path = output / "pointwise_mutual_information.csv"
    metrics_path = output / "information_metrics.json"
    summary_path = output / "information_summary.json"
    validation_path = output / "information_validation.json"
    observation_path = output / "information_observation.json"
    manifest_path = output / "sha256_manifest.json"

    _write_distribution(distribution_path, labels, metrics.source_distribution, metrics.target_distribution)
    _write_matrix(pmi_path, labels, metrics.pointwise_mutual_information_bits)

    metrics_dict = {
        "source_entropy_bits": metrics.source_entropy_bits,
        "target_entropy_bits": metrics.target_entropy_bits,
        "joint_entropy_bits": metrics.joint_entropy_bits,
        "conditional_entropy_bits": metrics.conditional_entropy_bits,
        "entropy_rate_bits": metrics.entropy_rate_bits,
        "mutual_information_bits": metrics.mutual_information_bits,
        "normalized_mutual_information": metrics.normalized_mutual_information,
        "target_redundancy": metrics.target_redundancy,
        "effective_target_alphabet": metrics.effective_target_alphabet,
        "predictability_fraction": metrics.predictability_fraction,
    }
    metrics_path.write_text(json.dumps(metrics_dict, indent=2), encoding="utf-8")

    checks = {
        "transition_count_positive": metrics.transition_count > 0,
        "joint_distribution_normalized": bool(np.isclose(metrics.joint_distribution.sum(), 1.0)),
        "source_distribution_normalized": bool(np.isclose(metrics.source_distribution.sum(), 1.0)),
        "target_distribution_normalized": bool(np.isclose(metrics.target_distribution.sum(), 1.0)),
        "conditional_rows_normalized": bool(np.allclose(metrics.conditional_probabilities[metrics.source_distribution > 0].sum(axis=1), 1.0)),
        "entropy_chain_rule": bool(np.isclose(metrics.joint_entropy_bits, metrics.source_entropy_bits + metrics.conditional_entropy_bits, atol=1e-10)),
        "mutual_information_identity": bool(np.isclose(metrics.mutual_information_bits, metrics.target_entropy_bits - metrics.conditional_entropy_bits, atol=1e-10)),
        "entropy_rate_bounds": 0.0 <= metrics.entropy_rate_bits <= metrics.target_entropy_bits + 1e-10,
        "normalized_metrics_bounds": 0.0 <= metrics.normalized_mutual_information <= 1.0 and 0.0 <= metrics.target_redundancy <= 1.0 and 0.0 <= metrics.predictability_fraction <= 1.0,
        "source_transition_count_match": metrics.transition_count == int(transition_summary["transitions_scanned"]),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    validation = {"status": status, "checks": checks}
    validation_path.write_text(json.dumps(validation, indent=2), encoding="utf-8")
    if status != "PASS":
        raise RuntimeError("Information observation validation failed.")

    created_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    runtime_seconds = time.perf_counter() - started
    summary = {
        "project": PROJECT,
        "instrument": "information_runner.py",
        "instrument_id": "IO-006",
        "observatory": OBSERVATORY_NAME,
        "version": VERSION,
        "algorithm": ALGORITHM,
        "algorithm_version": ALGORITHM_VERSION,
        "coordinate_system": transition_summary.get("coordinate_system", COORDINATE_SYSTEM),
        "start": int(transition_summary["numeric_domain_start"]),
        "end": int(transition_summary["numeric_domain_end"]),
        "transition_count": metrics.transition_count,
        "state_count": len(labels),
        "active_source_states": metrics.active_source_states,
        "active_target_states": metrics.active_target_states,
        "state_labels": list(labels),
        "information_metrics": metrics_dict,
        "validation": validation,
        "runtime": {"total_seconds": runtime_seconds, "total_minutes": runtime_seconds / 60.0},
        "inputs": {"transition_counts_csv": str(counts_path), "transition_summary_json": str(transition_summary_path)},
        "outputs": {"metrics_json": str(metrics_path), "distributions_csv": str(distribution_path), "pmi_csv": str(pmi_path), "validation_json": str(validation_path), "summary_json": str(summary_path), "observation_json": str(observation_path)},
        "source_transition_summary": transition_summary,
        "created_utc": created_utc,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "git_commit": _git(["rev-parse", "HEAD"]),
        "git_tag": _git(["describe", "--tags", "--exact-match"]),
        "command_line": " ".join(sys.argv),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    coordinate_system = str(summary["coordinate_system"])
    observation = build_transition_metrics_information_observation(
        observation_id=args.observation_id,
        coordinate_range=CoordinateRange(coordinate_system=coordinate_system, start=summary["start"], end=summary["end"]),
        summary=summary,
        created_utc=created_utc,
    )
    observation_path.write_text(json.dumps(_jsonable(observation), indent=2, default=_jsonable), encoding="utf-8")

    artifacts = [distribution_path, pmi_path, metrics_path, summary_path, validation_path, observation_path]
    manifest_path.write_text(json.dumps({path.name: _sha256(path) for path in artifacts}, indent=2), encoding="utf-8")
    return output


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run PrimeNet Information Observatory v1.0")
    p.add_argument("--transition-output-dir", required=True, help="Validated Transition Observatory output directory")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--observation-id", default="INFORMATION-V1")
    return p


def main() -> None:
    output = run(parser().parse_args())
    print("=" * 80)
    print("PrimeNet Information Observatory v1.0: PASSED")
    print(f"Output: {output}")
    print("=" * 80)


if __name__ == "__main__":
    main()
