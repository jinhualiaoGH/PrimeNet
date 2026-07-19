from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from observatories.framework import CoordinateRange, Observation

from .metadata import (
    ALGORITHM,
    ALGORITHM_VERSION,
    GAP_OWNERSHIP,
    OBSERVATORY_CATEGORY,
    OBSERVATORY_NAME,
    VERSION,
)


def _validate_common_arguments(
    *,
    observation_id: str,
    coordinate_range: CoordinateRange,
) -> None:
    if not isinstance(observation_id, str) or not observation_id.strip():
        raise ValueError("observation_id must be a non-empty string.")

    if not isinstance(coordinate_range, CoordinateRange):
        raise TypeError("coordinate_range must be a CoordinateRange.")


def _build_matrix_observation(
    *,
    observation_id: str,
    coordinate_range: CoordinateRange,
    matrix_summary: Mapping[str, Any],
    created_utc: str | None,
) -> Observation:
    """
    Preserve the PrimeNet v1.1 transition-matrix adapter contract.
    """
    required = {
        "observatory_id",
        "observatory_name",
        "observatory_category",
        "observatory_version",
        "input_file",
        "metrics",
        "validation",
    }

    missing = required.difference(matrix_summary)
    if missing:
        raise ValueError(
            "Transition matrix summary missing: "
            + ", ".join(sorted(missing))
        )

    if matrix_summary["observatory_id"] != "OBS-TRANSITION":
        raise ValueError(
            "Transition matrix summary has the wrong observatory identity: "
            f"{matrix_summary['observatory_id']!r}"
        )

    metrics = matrix_summary["metrics"]
    validation = matrix_summary["validation"]

    if not isinstance(metrics, Mapping):
        raise TypeError("matrix_summary['metrics'] must be a mapping.")

    if not isinstance(validation, Mapping):
        raise TypeError("matrix_summary['validation'] must be a mapping.")

    required_metrics = {
        "rows",
        "columns",
        "numeric_columns",
        "total_matrix_mass",
        "min_row_mass",
        "max_row_mass",
        "mean_row_mass",
        "min_column_mass",
        "max_column_mass",
        "mean_column_mass",
        "has_missing_values",
    }

    missing_metrics = required_metrics.difference(metrics)
    if missing_metrics:
        raise ValueError(
            "Transition matrix metrics missing: "
            + ", ".join(sorted(missing_metrics))
        )

    required_validation = {
        "rows",
        "columns",
        "empty",
        "has_missing_values",
        "column_names",
        "numeric_columns",
        "numeric_column_count",
        "min_value",
        "max_value",
        "total_mass",
    }

    missing_validation = required_validation.difference(validation)
    if missing_validation:
        raise ValueError(
            "Transition matrix validation missing: "
            + ", ".join(sorted(missing_validation))
        )

    if bool(validation["empty"]):
        raise ValueError("Transition matrix must not be empty.")

    if bool(metrics["has_missing_values"]):
        raise ValueError("Transition matrix contains missing values.")

    if bool(validation["has_missing_values"]):
        raise ValueError("Transition matrix validation found missing values.")

    if int(metrics["rows"]) != int(validation["rows"]):
        raise ValueError("Matrix row counts disagree.")

    if int(metrics["columns"]) != int(validation["columns"]):
        raise ValueError("Matrix column counts disagree.")

    if int(metrics["numeric_columns"]) != int(
        validation["numeric_column_count"]
    ):
        raise ValueError("Numeric matrix column counts disagree.")

    if float(metrics["total_matrix_mass"]) != float(
        validation["total_mass"]
    ):
        raise ValueError("Matrix total-mass values disagree.")

    arguments: dict[str, Any] = {
        "observation_id": observation_id,
        "observatory_name": str(matrix_summary["observatory_name"]),
        "title": "Transition Matrix Observation",
        "coordinate_range": coordinate_range,
        "parameters": {
            "matrix_category": str(
                matrix_summary["observatory_category"]
            ),
            "observatory_version": str(
                matrix_summary["observatory_version"]
            ),
            "input_file": str(matrix_summary["input_file"]),
            "numeric_columns": list(validation["numeric_columns"]),
        },
        "measurements": {
            "rows": int(metrics["rows"]),
            "columns": int(metrics["columns"]),
            "numeric_columns": int(metrics["numeric_columns"]),
            "has_missing_values": bool(
                metrics["has_missing_values"]
            ),
        },
        "statistics": {
            "total_matrix_mass": float(
                metrics["total_matrix_mass"]
            ),
            "min_row_mass": float(metrics["min_row_mass"]),
            "max_row_mass": float(metrics["max_row_mass"]),
            "mean_row_mass": float(metrics["mean_row_mass"]),
            "min_column_mass": float(metrics["min_column_mass"]),
            "max_column_mass": float(metrics["max_column_mass"]),
            "mean_column_mass": float(metrics["mean_column_mass"]),
        },
        "provenance": {
            "source_observatory_id": str(
                matrix_summary["observatory_id"]
            ),
            "source_observatory_name": str(
                matrix_summary["observatory_name"]
            ),
            "source_file": str(matrix_summary["input_file"]),
            "builder": "build_transition_observation",
            "adapter_contract": "transition-matrix-v1.1",
        },
    }

    if created_utc is not None:
        arguments["created_utc"] = created_utc

    return Observation(**arguments)


def _build_census_observation(
    *,
    observation_id: str,
    coordinate_range: CoordinateRange,
    summary: Mapping[str, Any],
    created_utc: str | None,
) -> Observation:
    """
    Build the canonical Transition Observatory v1.0 census observation.
    """
    required = {
        "numeric_domain_start",
        "numeric_domain_end",
        "gap_files_scanned",
        "gaps_scanned",
        "transitions_scanned",
        "state_count",
        "states",
        "overflow_label",
        "entropy_rate_bits",
        "runtime_seconds",
        "validation_status",
        "repository",
        "counts_csv",
        "probabilities_csv",
    }

    missing = required.difference(summary)
    if missing:
        raise ValueError(
            "Transition census summary missing: "
            + ", ".join(sorted(missing))
        )

    if int(summary["numeric_domain_start"]) != coordinate_range.start:
        raise ValueError(
            "CoordinateRange start disagrees with transition summary."
        )

    if int(summary["numeric_domain_end"]) != coordinate_range.end:
        raise ValueError(
            "CoordinateRange end disagrees with transition summary."
        )

    if summary["validation_status"] != "PASS":
        raise ValueError(
            "Only validated transition summaries may become observations."
        )

    states = list(summary["states"])

    if int(summary["state_count"]) != len(states) + 1:
        raise ValueError(
            "state_count must equal the canonical states plus overflow."
        )

    gaps_scanned = int(summary["gaps_scanned"])
    transitions_scanned = int(summary["transitions_scanned"])

    if gaps_scanned < 1:
        raise ValueError("gaps_scanned must be positive.")

    if transitions_scanned != gaps_scanned - 1:
        raise ValueError(
            "For one continuous gap stream, transitions_scanned must "
            "equal gaps_scanned - 1."
        )

    arguments: dict[str, Any] = {
        "observation_id": observation_id,
        "observatory_name": OBSERVATORY_NAME,
        "title": "Prime-Gap First-Order Transition Observation",
        "coordinate_range": coordinate_range,
        "parameters": {
            "observatory_category": OBSERVATORY_CATEGORY,
            "observatory_version": VERSION,
            "algorithm": ALGORITHM,
            "algorithm_version": ALGORITHM_VERSION,
            "transition_order": 1,
            "gap_ownership": GAP_OWNERSHIP,
            "states": states,
            "overflow_label": summary["overflow_label"],
        },
        "measurements": {
            "gap_files_scanned": int(
                summary["gap_files_scanned"]
            ),
            "gaps_scanned": gaps_scanned,
            "transitions_scanned": transitions_scanned,
            "state_count": int(summary["state_count"]),
        },
        "statistics": {
            "entropy_rate_bits": float(
                summary["entropy_rate_bits"]
            ),
            "spectral_gap": summary.get("spectral_gap"),
            "second_eigenvalue_modulus": summary.get(
                "second_eigenvalue_modulus"
            ),
            "runtime_seconds": float(
                summary["runtime_seconds"]
            ),
        },
        "provenance": {
            "repository": str(summary["repository"]),
            "counts_csv": str(summary["counts_csv"]),
            "probabilities_csv": str(
                summary["probabilities_csv"]
            ),
            "summary_json": str(
                summary.get("summary_json", "")
            ),
            "validation_status": "PASS",
            "builder": "build_transition_observation",
            "adapter_contract": "transition-census-v1.0",
        },
    }

    if created_utc is not None:
        arguments["created_utc"] = created_utc

    return Observation(**arguments)


def build_transition_observation(
    *,
    observation_id: str,
    coordinate_range: CoordinateRange,
    matrix_summary: Mapping[str, Any] | None = None,
    summary: Mapping[str, Any] | None = None,
    created_utc: str | None = None,
) -> Observation:
    """
    Build a canonical PrimeNet transition observation.

    Supported contracts:

    1. PrimeNet v1.1 transition-matrix adapter:
           matrix_summary=...

    2. Transition Observatory v1.0 full-census adapter:
           summary=...

    Exactly one summary argument must be supplied.
    """
    _validate_common_arguments(
        observation_id=observation_id,
        coordinate_range=coordinate_range,
    )

    supplied = int(matrix_summary is not None) + int(
        summary is not None
    )

    if supplied != 1:
        raise ValueError(
            "Supply exactly one of matrix_summary or summary."
        )

    if matrix_summary is not None:
        if not isinstance(matrix_summary, Mapping):
            raise TypeError("matrix_summary must be a mapping.")

        return _build_matrix_observation(
            observation_id=observation_id,
            coordinate_range=coordinate_range,
            matrix_summary=matrix_summary,
            created_utc=created_utc,
        )

    assert summary is not None

    if not isinstance(summary, Mapping):
        raise TypeError("summary must be a mapping.")

    return _build_census_observation(
        observation_id=observation_id,
        coordinate_range=coordinate_range,
        summary=summary,
        created_utc=created_utc,
    )
