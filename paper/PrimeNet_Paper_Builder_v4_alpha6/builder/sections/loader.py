from __future__ import annotations

import json
from pathlib import Path

from builder.core.exceptions import PipelineError

from .models import SectionSpec


class SectionSpecLoader:
    def __init__(self, plugin_root: Path) -> None:
        self.plugin_root = plugin_root.resolve()
        self.sections_root = self.plugin_root / "sections"

    def discover(self) -> tuple[SectionSpec, ...]:
        if not self.sections_root.exists():
            return ()
        specs = [self.load(path) for path in sorted(self.sections_root.glob("*.json"))]
        identifiers = [spec.section_id for spec in specs]
        if len(identifiers) != len(set(identifiers)):
            raise PipelineError("Duplicate section IDs detected.")
        return tuple(sorted(specs, key=lambda item: (item.order, item.section_id)))

    def load(self, path: Path) -> SectionSpec:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise PipelineError(f"Section specification not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise PipelineError(f"Invalid section specification JSON at {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise PipelineError(f"Section specification root must be an object: {path}")
        spec = SectionSpec.from_dict(payload)
        self.template_path(spec)
        return spec

    def template_path(self, spec: SectionSpec) -> Path:
        candidate = (self.plugin_root / spec.template).resolve()
        try:
            candidate.relative_to(self.plugin_root)
        except ValueError as exc:
            raise PipelineError(f"Section template escapes plugin root: {spec.template}") from exc
        if not candidate.is_file():
            raise PipelineError(f"Section template not found: {candidate}")
        return candidate
