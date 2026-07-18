from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from observatories.framework import CoordinateRange, Observation

from .metadata import (
    DESCRIPTION,
    NAME,
    OBSERVATORY_ID,
    VERSION,
)


_REQUIRED_SUMMARY_FIELDS = {
    "instrument",
    "version",
    "transition_matrix_path",
    "stationary_distribution_path",
    "num_states",
    "num_transitions_nonzero",
    "matched_states",
    "unmatched_states",
    "total_stationary_mass_used",
    "entropy_rate_bits_per_step",
    "max_contribution_state",
    "max_contribution_value",
}


def _validate_summary(summary: Mapping[str, Any]) -> None:
    if not isinstance(summary, Mapping):
        raise TypeError("summary must be a mapping.")

    missing = _REQUIRED_SUMMARY_FIELDS.difference(summary)

    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(
            f"Entropy-rate summary is missing: {missing_text}."
        )


def build_entropy_rate_observation(
    *,
    observation_id: str,
    coordinate_range: CoordinateRange,
    summary: Mapping[str, Any],
    created_utc: str | None = None,
) -> Observation:
    """
    Convert an EntropyRateInstrument summary into a canonical Observation.

    This function performs no scientific calculation and writes no files.
    """

    _validate_summary(summary)

    parameters = {
        "transition_matrix_path": str(
            Path(str(summary["transition_matrix_path"]))
        ),
        "stationary_distribution_path": str(
            Path(str(summary["stationary_distribution_path"]))
        ),
    }

    measurements = {
        "num_states": int(summary["num_states"]),
        "num_transitions_nonzero": int(
            summary["num_transitions_nonzero"]
        ),
        "matched_states": int(summary["matched_states"]),
        "unmatched_states": int(summary["unmatched_states"]),
    }

    statistics = {
        "entropy_rate_bits_per_step": float(
            summary["entropy_rate_bits_per_step"]
        ),
        "total_stationary_mass_used": float(
            summary["total_stationary_mass_used"]
        ),
        "max_contribution_state": summary[
            "max_contribution_state"
        ],
        "max_contribution_value": summary[
            "max_contribution_value"
        ],
    }

    provenance = {
        "observatory_id": OBSERVATORY_ID,
        "observatory_version": VERSION,
        "instrument": str(summary["instrument"]),
        "instrument_version": str(summary["version"]),
        "description": DESCRIPTION,
    }

    arguments: dict[str, Any] = {
        "observation_id": observation_id,
        "observatory_name": NAME,
        "title": "Prime-Gap Transition Entropy Rate",
        "coordinate_range": coordinate_range,
        "parameters": parameters,
        "measurements": measurements,
        "statistics": statistics,
        "provenance": provenance,
    }

    if created_utc is not None:
        arguments["created_utc"] = created_utc

    return Observation(**arguments)
