from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from observatories.framework import CoordinateRange, Observation
from .metadata import ALGORITHM, ALGORITHM_VERSION, OBSERVATORY_NAME, VERSION


def build_geometry_observation(
    *, observation_id: str, coordinate_range: CoordinateRange,
    summary: Mapping[str, Any], created_utc: str | None = None,
) -> Observation:
    required = {"start", "end", "active_state_count", "cluster_count", "geometry_metrics", "validation", "inputs", "outputs"}
    missing = required.difference(summary)
    if missing:
        raise ValueError("Geometry summary missing: " + ", ".join(sorted(missing)))
    if summary["validation"].get("status") != "PASS":
        raise ValueError("Only validated geometry summaries may become observations.")
    if int(summary["start"]) != coordinate_range.start or int(summary["end"]) != coordinate_range.end:
        raise ValueError("Coordinate range disagrees with geometry summary.")
    metrics = summary["geometry_metrics"]
    args = {
        "observation_id": observation_id,
        "observatory_name": OBSERVATORY_NAME,
        "title": "Prime-Gap Information Geometry Observation",
        "coordinate_range": coordinate_range,
        "parameters": {
            "observatory_version": VERSION,
            "algorithm": ALGORITHM,
            "algorithm_version": ALGORITHM_VERSION,
            "distance": "0.5 Jensen-Shannon + 0.5 Hellinger",
            "embedding": "classical multidimensional scaling",
            "clustering": "deterministic average linkage",
        },
        "measurements": {
            "active_state_count": int(summary["active_state_count"]),
            "cluster_count": int(summary["cluster_count"]),
        },
        "statistics": dict(metrics),
        "provenance": {
            "source_information_summary": str(summary["inputs"]["information_summary_json"]),
            "source_transition_counts": str(summary["inputs"]["transition_counts_csv"]),
            "summary_json": str(summary["outputs"]["summary_json"]),
            "validation_status": "PASS",
        },
    }
    if created_utc is not None:
        args["created_utc"] = created_utc
    return Observation(**args)
