from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .coordinate_range import CoordinateRange
from .observation import Observation


_REQUIRED_TOP_LEVEL_FIELDS = {
    "observatory_id",
    "observatory_name",
    "observatory_category",
    "observatory_version",
    "input_file",
    "metrics",
    "validation",
}

_REQUIRED_METRIC_FIELDS = {
    "rows",
    "columns",
    "numeric_columns",
}

_REQUIRED_VALIDATION_FIELDS = {
    "rows",
    "columns",
    "empty",
    "has_missing_values",
    "column_names",
    "numeric_columns",
    "numeric_column_count",
}


def build_matrix_observation(
    *,
    observation_id: str,
    coordinate_range: CoordinateRange,
    matrix_summary: Mapping[str, Any],
    title: str | None = None,
    created_utc: str | None = None,
) -> Observation:
    """
    Convert a MatrixObservatory summary into a canonical Observation.

    This function performs no scientific computation and no file-system
    operations. It only validates and maps an existing matrix summary.
    """
    if not isinstance(observation_id, str):
        raise TypeError("observation_id must be a string.")

    if not observation_id.strip():
        raise ValueError("observation_id must not be empty.")

    if not isinstance(coordinate_range, CoordinateRange):
        raise TypeError(
            "coordinate_range must be a CoordinateRange."
        )

    if not isinstance(matrix_summary, Mapping):
        raise TypeError("matrix_summary must be a mapping.")

    missing = _REQUIRED_TOP_LEVEL_FIELDS.difference(matrix_summary)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(
            f"Matrix summary is missing required fields: "
            f"{missing_text}."
        )

    metrics = matrix_summary["metrics"]
    validation = matrix_summary["validation"]

    if not isinstance(metrics, Mapping):
        raise ValueError("matrix_summary.metrics must be a mapping.")

    if not isinstance(validation, Mapping):
        raise ValueError(
            "matrix_summary.validation must be a mapping."
        )

    missing_metrics = _REQUIRED_METRIC_FIELDS.difference(metrics)
    if missing_metrics:
        missing_text = ", ".join(sorted(missing_metrics))
        raise ValueError(
            f"Matrix metrics are missing required fields: "
            f"{missing_text}."
        )

    missing_validation = (
        _REQUIRED_VALIDATION_FIELDS.difference(validation)
    )
    if missing_validation:
        missing_text = ", ".join(sorted(missing_validation))
        raise ValueError(
            f"Matrix validation is missing required fields: "
            f"{missing_text}."
        )

    rows = int(metrics["rows"])
    columns = int(metrics["columns"])
    numeric_column_count = int(metrics["numeric_columns"])

    if rows < 1:
        raise ValueError("Matrix row count must be positive.")

    if columns < 1:
        raise ValueError("Matrix column count must be positive.")

    if numeric_column_count < 0:
        raise ValueError(
            "Matrix numeric column count must not be negative."
        )

    if int(validation["rows"]) != rows:
        raise ValueError(
            "Matrix row count disagrees with validation."
        )

    if int(validation["columns"]) != columns:
        raise ValueError(
            "Matrix column count disagrees with validation."
        )

    if int(validation["numeric_column_count"]) != numeric_column_count:
        raise ValueError(
            "Numeric column count disagrees with validation."
        )

    observatory_name = str(matrix_summary["observatory_name"])
    observatory_category = str(
        matrix_summary["observatory_category"]
    )
    observatory_version = str(
        matrix_summary["observatory_version"]
    )
    input_file = str(matrix_summary["input_file"])

    observation_title = (
        title
        if title is not None
        else f"{observatory_name} Matrix Observation"
    )

    measurements: dict[str, Any] = {
        "rows": rows,
        "columns": columns,
        "numeric_column_count": numeric_column_count,
        "column_names": list(validation["column_names"]),
        "numeric_columns": list(validation["numeric_columns"]),
    }

    statistics = {
        key: value
        for key, value in metrics.items()
        if key not in {
            "rows",
            "columns",
            "numeric_columns",
        }
    }

    statistics.update(
        {
            "empty": bool(validation["empty"]),
            "has_missing_values": bool(
                validation["has_missing_values"]
            ),
        }
    )

    for key in ("min_value", "max_value", "total_mass"):
        if key in validation:
            statistics[f"validation_{key}"] = validation[key]

    provenance = {
        "source_observatory_id": str(
            matrix_summary["observatory_id"]
        ),
        "source_observatory_name": observatory_name,
        "source_observatory_category": observatory_category,
        "source_observatory_version": observatory_version,
        "input_file": input_file,
        "builder": "build_matrix_observation",
    }

    arguments: dict[str, Any] = {
        "observation_id": observation_id,
        "observatory_name": observatory_name,
        "title": observation_title,
        "coordinate_range": coordinate_range,
        "parameters": {
            "matrix_category": observatory_category,
        },
        "measurements": measurements,
        "statistics": statistics,
        "provenance": provenance,
    }

    if created_utc is not None:
        arguments["created_utc"] = created_utc

    return Observation(**arguments)
