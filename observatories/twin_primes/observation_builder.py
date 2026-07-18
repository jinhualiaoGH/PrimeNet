from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from observatories.framework import CoordinateRange, Observation

from .metadata import (
    EVENT_DEFINITION,
    INSTRUMENT,
    OBSERVATORY_CATEGORY,
    OBSERVATORY_NAME,
    PROJECT,
    VERSION,
)


_REQUIRED_FIELDS = {
    "project",
    "instrument",
    "version",
    "repository",
    "repository_status",
    "numeric_domain_start",
    "numeric_domain_end",
    "event_definition",
    "gap_files_scanned",
    "total_gaps_scanned",
    "total_twin_prime_events",
    "global_twin_density",
    "runtime_seconds",
    "runtime_minutes",
    "csv_output",
    "generated_at_utc",
}


def _canonical_utc_timestamp(value: Any) -> str:
    """Validate an ISO-8601 timestamp and normalize UTC to a trailing Z."""
    if not isinstance(value, str):
        raise TypeError("generated_at_utc must be a string.")

    text = value.strip()
    if not text:
        raise ValueError("generated_at_utc must not be empty.")

    parse_text = text[:-1] + "+00:00" if text.endswith("Z") else text

    try:
        parsed = datetime.fromisoformat(parse_text)
    except ValueError as exc:
        raise ValueError(
            "generated_at_utc must be a valid ISO-8601 timestamp."
        ) from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("generated_at_utc must include a UTC offset.")

    if parsed.utcoffset().total_seconds() != 0:
        raise ValueError("generated_at_utc must represent UTC.")

    return text[:-6] + "Z" if text.endswith("+00:00") else text


def build_twin_prime_observation(
    *,
    observation_id: str,
    coordinate_range: CoordinateRange,
    summary: Mapping[str, Any],
    created_utc: str | None = None,
) -> Observation:
    """
    Convert a completed Twin Prime Census summary into an Observation.

    This adapter performs no prime or gap computation and no file-system
    operations. It validates the accepted census summary, checks its numeric
    domain against the supplied CoordinateRange, and preserves the scientific
    counts, density, runtime, and repository provenance.
    """
    if not isinstance(observation_id, str):
        raise TypeError("observation_id must be a string.")

    if not observation_id.strip():
        raise ValueError("observation_id must not be empty.")

    if not isinstance(coordinate_range, CoordinateRange):
        raise TypeError("coordinate_range must be a CoordinateRange.")

    if not isinstance(summary, Mapping):
        raise TypeError("summary must be a mapping.")

    missing = _REQUIRED_FIELDS.difference(summary)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(
            "Twin Prime Census summary is missing required fields: "
            f"{missing_text}."
        )

    expected_identity = {
        "project": PROJECT,
        "instrument": INSTRUMENT,
        "version": VERSION,
        "event_definition": EVENT_DEFINITION,
        "repository_status": "ACCEPTED",
    }

    for field_name, expected_value in expected_identity.items():
        actual_value = summary[field_name]
        if actual_value != expected_value:
            raise ValueError(
                f"Twin Prime Census field {field_name!r} has value "
                f"{actual_value!r}; expected {expected_value!r}."
            )

    domain_start = int(summary["numeric_domain_start"])
    domain_end = int(summary["numeric_domain_end"])

    if coordinate_range.start != domain_start:
        raise ValueError(
            "CoordinateRange start disagrees with numeric_domain_start."
        )

    if coordinate_range.end != domain_end:
        raise ValueError(
            "CoordinateRange end disagrees with numeric_domain_end."
        )

    gap_files_scanned = int(summary["gap_files_scanned"])
    total_gaps_scanned = int(summary["total_gaps_scanned"])
    total_twin_prime_events = int(summary["total_twin_prime_events"])
    global_twin_density = float(summary["global_twin_density"])
    runtime_seconds = float(summary["runtime_seconds"])
    runtime_minutes = float(summary["runtime_minutes"])

    if gap_files_scanned < 1:
        raise ValueError("gap_files_scanned must be positive.")

    if total_gaps_scanned < 1:
        raise ValueError("total_gaps_scanned must be positive.")

    if total_twin_prime_events < 0:
        raise ValueError("total_twin_prime_events must not be negative.")

    if total_twin_prime_events > total_gaps_scanned:
        raise ValueError(
            "total_twin_prime_events must not exceed total_gaps_scanned."
        )

    if not 0.0 <= global_twin_density <= 1.0:
        raise ValueError("global_twin_density must lie in [0, 1].")

    reconstructed_density = total_twin_prime_events / total_gaps_scanned
    if abs(reconstructed_density - global_twin_density) > 1e-15:
        raise ValueError(
            "global_twin_density disagrees with the census counts."
        )

    if runtime_seconds < 0.0 or runtime_minutes < 0.0:
        raise ValueError("Runtime values must not be negative.")

    if abs(runtime_seconds / 60.0 - runtime_minutes) > 1e-9:
        raise ValueError(
            "runtime_minutes disagrees with runtime_seconds."
        )

    source_generated_utc = _canonical_utc_timestamp(
        summary["generated_at_utc"]
    )

    arguments: dict[str, Any] = {
        "observation_id": observation_id,
        "observatory_name": OBSERVATORY_NAME,
        "title": "Twin Prime Census Observation",
        "coordinate_range": coordinate_range,
        "parameters": {
            "observatory_category": OBSERVATORY_CATEGORY,
            "event_definition": EVENT_DEFINITION,
            "repository_status_required": "ACCEPTED",
        },
        "measurements": {
            "gap_files_scanned": gap_files_scanned,
            "total_gaps_scanned": total_gaps_scanned,
            "total_twin_prime_events": total_twin_prime_events,
        },
        "statistics": {
            "global_twin_density": global_twin_density,
            "runtime_seconds": runtime_seconds,
            "runtime_minutes": runtime_minutes,
        },
        "provenance": {
            "project": PROJECT,
            "instrument": INSTRUMENT,
            "instrument_version": VERSION,
            "repository": str(summary["repository"]),
            "repository_status": str(summary["repository_status"]),
            "csv_output": str(summary["csv_output"]),
            "source_generated_at_utc": source_generated_utc,
            "builder": "build_twin_prime_observation",
        },
    }

    if created_utc is not None:
        arguments["created_utc"] = created_utc

    return Observation(**arguments)
