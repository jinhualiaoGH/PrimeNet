from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping

from builder.core.exceptions import PipelineError
from builder.evidence import EvidenceLoader, EvidenceRegistry

from .models import RenderedTable, TableColumn, TableSpec


def _format(value: Any, column: TableColumn) -> str:
    if value is None:
        return ""
    if column.format == "integer":
        return f"{int(value):,}"
    if column.format == "number":
        return f"{float(value):,.6g}"
    if column.format == "scientific":
        return f"{float(value):.6e}"
    return str(value)


class TableRenderer:
    def __init__(self, registry: EvidenceRegistry, loader: EvidenceLoader) -> None:
        self.registry = registry
        self.loader = loader

    def render(self, spec: TableSpec, output_root: Path) -> RenderedTable:
        registered = self.registry.get(spec.evidence_id)
        data = self.loader.load_payload(registered.package, registered.record)
        rows = self._rows(data)
        raw_rows = [{column.key: row.get(column.key) for column in spec.columns} for row in rows]
        display_rows = [
            {column.title: _format(row.get(column.key), column) for column in spec.columns}
            for row in rows
        ]
        output_root.mkdir(parents=True, exist_ok=True)
        markdown_path = output_root / f"{spec.table_id}.md"
        csv_path = output_root / f"{spec.table_id}.csv"
        json_path = output_root / f"{spec.table_id}.json"
        markdown_path.write_text(self._markdown(spec, display_rows), encoding="utf-8")
        with csv_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=[column.key for column in spec.columns])
            writer.writeheader()
            writer.writerows(raw_rows)
        json_path.write_text(
            json.dumps({"id": spec.table_id, "title": spec.title, "rows": raw_rows}, indent=2),
            encoding="utf-8",
        )
        return RenderedTable(spec.table_id, markdown_path, csv_path, json_path, len(rows))

    @staticmethod
    def _rows(data: Any) -> list[Mapping[str, Any]]:
        if isinstance(data, Mapping):
            return [data]
        if isinstance(data, list) and all(isinstance(item, Mapping) for item in data):
            return list(data)
        raise PipelineError("Table evidence must be a JSON object or a list of JSON objects.")

    @staticmethod
    def _markdown(spec: TableSpec, rows: list[Mapping[str, str]]) -> str:
        headers = [column.title for column in spec.columns]
        lines = [f"# {spec.title}", ""]
        if spec.caption:
            lines.extend([spec.caption, ""])
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join("---" for _ in headers) + " |")
        for row in rows:
            values = [str(row.get(header, "")).replace("|", "\\|") for header in headers]
            lines.append("| " + " | ".join(values) + " |")
        lines.append("")
        return "\n".join(lines)
