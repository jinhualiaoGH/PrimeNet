from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from observatories.framework import (
    CoordinateRange,
    Observation,
    build_matrix_observation,
)

from .metadata import (
    CATEGORY,
    NAME,
    OBSERVATORY_ID,
    VERSION,
)


_REQUIRED_IDENTITY_FIELDS = {
    "observatory_id",
    "observatory_name",
    "observatory_category",
    "observatory_version",
}


def build_transition_observation(
    *,
    observation_id: str,
    coordinate_range: CoordinateRange,
    matrix_summary: Mapping[str, Any],
    created_utc: str | None = None,
) -> Observation:
    """
    Convert a Transition Observatory matrix summary into an Observation.

    This adapter performs no scientific calculations and no file-system
    operations. It validates Transition Observatory identity and delegates
    generic matrix mapping to build_matrix_observation().
    """
    if not isinstance(matrix_summary, Mapping):
        raise TypeError("matrix_summary must be a mapping.")

    missing = _REQUIRED_IDENTITY_FIELDS.difference(matrix_summary)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(
            "Transition matrix summary is missing identity fields: "
            f"{missing_text}."
        )

    expected_identity = {
        "observatory_id": OBSERVATORY_ID,
        "observatory_name": NAME,
        "observatory_category": CATEGORY,
        "observatory_version": VERSION,
    }

    for field_name, expected_value in expected_identity.items():
        actual_value = matrix_summary[field_name]

        if actual_value != expected_value:
            raise ValueError(
                f"Transition summary field {field_name!r} has value "
                f"{actual_value!r}; expected {expected_value!r}."
            )

    return build_matrix_observation(
        observation_id=observation_id,
        coordinate_range=coordinate_range,
        matrix_summary=matrix_summary,
        title="Transition Matrix Observation",
        created_utc=created_utc,
    )
