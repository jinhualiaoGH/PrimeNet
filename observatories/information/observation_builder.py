from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from observatories.framework import CoordinateRange, Observation

from .metadata import OBSERVATORY_CATEGORY, OBSERVATORY_NAME, SUPPORTED_INSTRUMENTS

_COMMON_REQUIRED_FIELDS = {
    "instrument", "instrument_id", "observatory", "version", "start", "end",
}
_KIND_REQUIRED_FIELDS = {
    "entropy": {"gap", "prime_count", "gap_summary", "orders", "runtime"},
    "transition": {"prime_count", "gap_count", "selected_state_count", "selected_states", "spectral_summary", "runtime"},
    "information_geometry": {"prime_count", "gap_count", "selected_state_count", "selected_states", "geometry_summary", "runtime"},
    "invariants": {"prime_count", "gap_count", "selected_state_count", "selected_states", "invariant_summary", "runtime"},
    "taxonomy": {"top_n", "even_only", "inputs", "taxonomy_summary", "runtime"},
    "transition_information": {
        "transition_count", "state_count", "information_metrics", "validation", "runtime"
    },
}


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"summary.{field_name} must be a mapping.")
    return value


def _validate_summary(summary: Mapping[str, Any], coordinate_range: CoordinateRange, expected_kind: str | None) -> str:
    if not isinstance(summary, Mapping):
        raise TypeError("summary must be a mapping.")
    missing = _COMMON_REQUIRED_FIELDS.difference(summary)
    if missing:
        raise ValueError("Information summary is missing required fields: " + ", ".join(sorted(missing)) + ".")
    if summary["observatory"] != OBSERVATORY_NAME:
        raise ValueError(f"summary.observatory must be {OBSERVATORY_NAME!r}.")
    instrument_id = str(summary["instrument_id"])
    if instrument_id not in SUPPORTED_INSTRUMENTS:
        raise ValueError(f"Unsupported Information instrument_id: {instrument_id!r}.")
    kind = SUPPORTED_INSTRUMENTS[instrument_id]
    if expected_kind is not None and kind != expected_kind:
        raise ValueError(f"Expected Information summary kind {expected_kind!r}; received {kind!r}.")
    missing_kind = _KIND_REQUIRED_FIELDS[kind].difference(summary)
    if missing_kind:
        raise ValueError(f"{kind} summary is missing required fields: " + ", ".join(sorted(missing_kind)) + ".")
    start, end = int(summary["start"]), int(summary["end"])
    if start != coordinate_range.start or end != coordinate_range.end:
        raise ValueError(
            "Information summary range does not match coordinate_range: "
            f"summary={start}..{end}, coordinate_range={coordinate_range.start}..{coordinate_range.end}."
        )
    _require_mapping(summary["runtime"], "runtime")
    if kind == "transition_information":
        metrics = _require_mapping(summary["information_metrics"], "information_metrics")
        validation = _require_mapping(summary["validation"], "validation")
        if validation.get("status") != "PASS":
            raise ValueError("Only validated transition-information summaries may become observations.")
        required_metrics = {
            "source_entropy_bits", "target_entropy_bits", "joint_entropy_bits",
            "conditional_entropy_bits", "entropy_rate_bits", "mutual_information_bits",
            "normalized_mutual_information", "target_redundancy",
            "effective_target_alphabet", "predictability_fraction",
        }
        absent = required_metrics.difference(metrics)
        if absent:
            raise ValueError("information_metrics missing: " + ", ".join(sorted(absent)) + ".")
    return kind


def _optional_parameters(summary: Mapping[str, Any]) -> dict[str, Any]:
    keys = ("gap", "max_order", "top_n", "max_gap", "even_only", "selected_states", "event_language_definition", "state_labels")
    return {key: summary[key] for key in keys if key in summary}


def _measurements(summary: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in ("prime_count", "gap_count", "selected_state_count", "event_language_length", "event_count", "total_selected_transitions", "nonzero_source_rows", "transition_count", "state_count", "active_source_states", "active_target_states"):
        if key in summary:
            result[key] = summary[key]
    gap_summary = summary.get("gap_summary")
    if gap_summary is not None:
        mapping = _require_mapping(gap_summary, "gap_summary")
        if "gap_count" in mapping:
            result.setdefault("gap_count", mapping["gap_count"])
    taxonomy_summary = summary.get("taxonomy_summary")
    if taxonomy_summary is not None:
        mapping = _require_mapping(taxonomy_summary, "taxonomy_summary")
        if "gap_count" in mapping:
            result.setdefault("classified_gap_count", mapping["gap_count"])
    return result


def _statistics(summary: Mapping[str, Any], kind: str) -> dict[str, Any]:
    result: dict[str, Any] = {"analysis_kind": kind}
    for key in ("gap_min", "gap_max", "gap_mean", "event_density", "transition_matrix_density"):
        if key in summary:
            result[key] = summary[key]
    for key in ("gap_summary", "orders", "spectral_summary", "geometry_summary", "invariant_summary", "taxonomy_summary", "information_metrics", "runtime"):
        if key in summary:
            result[key] = summary[key]
    return result


def _provenance(summary: Mapping[str, Any], kind: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source_observatory": OBSERVATORY_NAME,
        "source_instrument": str(summary["instrument"]),
        "source_instrument_id": str(summary["instrument_id"]),
        "source_instrument_version": str(summary["version"]),
        "analysis_kind": kind,
        "builder": "build_information_observation",
    }
    for key in ("created_utc", "prime_file", "event_file", "inputs", "outputs", "python_version", "platform", "numpy_version", "git_commit", "git_tag", "command_line", "source_transition_summary"):
        if key in summary:
            result[key] = summary[key]
    return result


def build_information_observation(*, observation_id: str, coordinate_range: CoordinateRange, summary: Mapping[str, Any], expected_kind: str | None = None, created_utc: str | None = None) -> Observation:
    if not isinstance(observation_id, str):
        raise TypeError("observation_id must be a string.")
    if not observation_id.strip():
        raise ValueError("observation_id must not be empty.")
    if not isinstance(coordinate_range, CoordinateRange):
        raise TypeError("coordinate_range must be a CoordinateRange.")
    kind = _validate_summary(summary, coordinate_range, expected_kind)
    title = f"Information Observatory: {kind.replace('_', ' ').title()}"
    arguments: dict[str, Any] = {
        "observation_id": observation_id,
        "observatory_name": OBSERVATORY_NAME,
        "title": title,
        "coordinate_range": coordinate_range,
        "parameters": {"observatory_category": OBSERVATORY_CATEGORY, "analysis_kind": kind, **_optional_parameters(summary)},
        "measurements": _measurements(summary),
        "statistics": _statistics(summary, kind),
        "provenance": _provenance(summary, kind),
    }
    if created_utc is not None:
        arguments["created_utc"] = created_utc
    return Observation(**arguments)


def build_entropy_information_observation(**kwargs: Any) -> Observation:
    return build_information_observation(expected_kind="entropy", **kwargs)

def build_transition_information_observation(**kwargs: Any) -> Observation:
    return build_information_observation(expected_kind="transition", **kwargs)

def build_geometry_information_observation(**kwargs: Any) -> Observation:
    return build_information_observation(expected_kind="information_geometry", **kwargs)

def build_invariant_information_observation(**kwargs: Any) -> Observation:
    return build_information_observation(expected_kind="invariants", **kwargs)

def build_taxonomy_information_observation(**kwargs: Any) -> Observation:
    return build_information_observation(expected_kind="taxonomy", **kwargs)

def build_transition_metrics_information_observation(**kwargs: Any) -> Observation:
    return build_information_observation(expected_kind="transition_information", **kwargs)
