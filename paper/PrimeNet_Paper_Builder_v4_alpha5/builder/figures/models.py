from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from builder.core.exceptions import PipelineError

_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_ALLOWED_KINDS = {"bar", "line"}
_ALLOWED_ORIENTATIONS = {"vertical", "horizontal"}
_ALLOWED_SCALES = {"linear", "log"}


@dataclass(frozen=True, slots=True)
class FigureSeries:
    key: str
    label: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FigureSeries":
        key = str(payload.get("key", "")).strip()
        label = str(payload.get("label", "")).strip()
        if not key or not label:
            raise PipelineError("Figure series requires non-empty key and label values.")
        return cls(key=key, label=label)


@dataclass(frozen=True, slots=True)
class FigureSpec:
    figure_id: str
    title: str
    evidence_id: str
    kind: str
    series: tuple[FigureSeries, ...]
    caption: str = ""
    x_label: str = ""
    y_label: str = ""
    orientation: str = "vertical"
    value_scale: str = "linear"
    width: float = 8.0
    height: float = 5.0
    dpi: int = 180

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FigureSpec":
        figure_id = str(payload.get("id", "")).strip()
        title = str(payload.get("title", "")).strip()
        evidence_id = str(payload.get("evidence_id", "")).strip()
        kind = str(payload.get("kind", "bar")).strip().lower()
        orientation = str(payload.get("orientation", "vertical")).strip().lower()
        value_scale = str(payload.get("value_scale", "linear")).strip().lower()
        series_raw = payload.get("series", [])
        if not _ID_PATTERN.fullmatch(figure_id):
            raise PipelineError(f"Invalid figure id: {figure_id!r}")
        if not title or not evidence_id:
            raise PipelineError(f"Figure {figure_id!r} requires title and evidence_id.")
        if kind not in _ALLOWED_KINDS:
            raise PipelineError(f"Figure {figure_id!r} kind must be one of: {sorted(_ALLOWED_KINDS)}")
        if orientation not in _ALLOWED_ORIENTATIONS:
            raise PipelineError(
                f"Figure {figure_id!r} orientation must be one of: {sorted(_ALLOWED_ORIENTATIONS)}"
            )
        if value_scale not in _ALLOWED_SCALES:
            raise PipelineError(f"Figure {figure_id!r} value_scale must be one of: {sorted(_ALLOWED_SCALES)}")
        if not isinstance(series_raw, list) or not series_raw:
            raise PipelineError(f"Figure {figure_id!r} requires a non-empty series list.")
        series = tuple(FigureSeries.from_dict(item) for item in series_raw)
        width = float(payload.get("width", 8.0))
        height = float(payload.get("height", 5.0))
        dpi = int(payload.get("dpi", 180))
        if width <= 0 or height <= 0 or dpi < 72:
            raise PipelineError(f"Figure {figure_id!r} has invalid dimensions or dpi.")
        return cls(
            figure_id=figure_id,
            title=title,
            evidence_id=evidence_id,
            kind=kind,
            series=series,
            caption=str(payload.get("caption", "")).strip(),
            x_label=str(payload.get("x_label", "")).strip(),
            y_label=str(payload.get("y_label", "")).strip(),
            orientation=orientation,
            value_scale=value_scale,
            width=width,
            height=height,
            dpi=dpi,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = payload.pop("figure_id")
        return payload


@dataclass(frozen=True, slots=True)
class RenderedFigure:
    figure_id: str
    png_path: Path
    svg_path: Path
    metadata_path: Path
    point_count: int
