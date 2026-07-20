from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from builder.core.exceptions import PipelineError
from builder.evidence import EvidenceLoader, EvidenceRegistry

from .loader import SectionSpecLoader
from .models import RenderedSection, SectionSpec

_TOKEN = re.compile(r"\{\{\s*(evidence|table|figure):([^{}]+?)\s*\}\}")


class SectionRenderer:
    def __init__(
        self,
        registry: EvidenceRegistry,
        evidence_loader: EvidenceLoader,
        plugin_root: Path,
        build_dir: Path,
        *,
        strict: bool = True,
    ) -> None:
        self.registry = registry
        self.evidence_loader = evidence_loader
        self.spec_loader = SectionSpecLoader(plugin_root)
        self.build_dir = build_dir.resolve()
        self.strict = strict

    def render(self, spec: SectionSpec, output_root: Path) -> RenderedSection:
        template_path = self.spec_loader.template_path(spec)
        template = template_path.read_text(encoding="utf-8")
        unresolved: list[str] = []

        def replace(match: re.Match[str]) -> str:
            kind, expression = match.group(1), match.group(2).strip()
            try:
                if kind == "evidence":
                    return self._render_evidence(expression)
                if kind == "table":
                    return self._render_table(expression)
                if kind == "figure":
                    return self._render_figure(expression)
            except PipelineError:
                if self.strict:
                    raise
                unresolved.append(match.group(0))
                return match.group(0)
            raise PipelineError(f"Unsupported section token: {kind}")

        body = _TOKEN.sub(replace, template)
        heading = f"{'#' * spec.level} {spec.title}\n\n"
        output_root.mkdir(parents=True, exist_ok=True)
        output_path = output_root / f"{spec.order:03d}_{spec.section_id}.md"
        output_path.write_text(heading + body.rstrip() + "\n", encoding="utf-8")
        return RenderedSection(spec.section_id, output_path, spec.order, len(unresolved))

    def _render_evidence(self, expression: str) -> str:
        evidence_id, separator, field_path = expression.partition("|")
        evidence_id = evidence_id.strip()
        registered = self.registry.get(evidence_id)
        payload = self.evidence_loader.load_payload(registered.package, registered.record)
        if not separator:
            if isinstance(payload, (dict, list)):
                return "```json\n" + json.dumps(payload, indent=2, sort_keys=True) + "\n```"
            return str(payload)
        value: Any = payload
        for key in (part.strip() for part in field_path.split(".")):
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                raise PipelineError(f"Evidence field not found: {evidence_id}|{field_path}")
        if isinstance(value, int):
            return f"{value:,}"
        if isinstance(value, float):
            return f"{value:,g}"
        if isinstance(value, (dict, list)):
            return json.dumps(value, sort_keys=True)
        return str(value)

    def _render_table(self, table_id: str) -> str:
        path = self.build_dir / "tables" / f"{table_id.strip()}.md"
        if not path.is_file():
            raise PipelineError(f"Rendered table not found for section token: {table_id}")
        return path.read_text(encoding="utf-8").strip()

    def _render_figure(self, figure_id: str) -> str:
        figure_id = figure_id.strip()
        metadata_path = self.build_dir / "figures" / f"{figure_id}.json"
        png_path = self.build_dir / "figures" / f"{figure_id}.png"
        if not metadata_path.is_file() or not png_path.is_file():
            raise PipelineError(f"Rendered figure not found for section token: {figure_id}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        caption = str(metadata.get("caption", "")).strip()
        relative = Path("..") / "figures" / png_path.name
        image = f"![{caption or figure_id}]({relative.as_posix()})"
        return image + (f"\n\n*{caption}*" if caption else "")
