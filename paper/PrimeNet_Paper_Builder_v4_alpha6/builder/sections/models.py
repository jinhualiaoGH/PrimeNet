from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from builder.core.exceptions import PipelineError

_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_ALLOWED_LEVELS = {1, 2, 3, 4, 5, 6}


@dataclass(frozen=True, slots=True)
class SectionSpec:
    section_id: str
    title: str
    order: int
    template: str
    level: int = 1

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SectionSpec":
        section_id = str(payload.get("id", "")).strip()
        title = str(payload.get("title", "")).strip()
        template = str(payload.get("template", "")).strip()
        if not _ID_PATTERN.fullmatch(section_id):
            raise PipelineError(f"Invalid section id: {section_id!r}")
        if not title or not template:
            raise PipelineError(f"Section {section_id!r} requires title and template.")
        if Path(template).is_absolute():
            raise PipelineError(f"Section {section_id!r} template must be plugin-relative.")
        order = int(payload.get("order", 0))
        level = int(payload.get("level", 1))
        if order < 0:
            raise PipelineError(f"Section {section_id!r} order must be non-negative.")
        if level not in _ALLOWED_LEVELS:
            raise PipelineError(f"Section {section_id!r} level must be between 1 and 6.")
        return cls(section_id=section_id, title=title, order=order, template=template, level=level)


@dataclass(frozen=True, slots=True)
class RenderedSection:
    section_id: str
    markdown_path: Path
    order: int
    unresolved_count: int
