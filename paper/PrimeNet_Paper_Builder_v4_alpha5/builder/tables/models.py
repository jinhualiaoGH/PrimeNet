from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from builder.core.exceptions import PipelineError

_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


@dataclass(frozen=True, slots=True)
class TableColumn:
    key: str
    title: str
    format: str = "text"

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TableColumn":
        key = str(payload.get("key", "")).strip()
        title = str(payload.get("title", "")).strip()
        fmt = str(payload.get("format", "text")).strip()
        if not key or not title:
            raise PipelineError("Table columns require key and title.")
        if fmt not in {"text", "integer", "number", "scientific"}:
            raise PipelineError(f"Unsupported table column format: {fmt}")
        return cls(key=key, title=title, format=fmt)


@dataclass(frozen=True, slots=True)
class TableSpec:
    table_id: str
    title: str
    evidence_id: str
    columns: tuple[TableColumn, ...]
    caption: str = ""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TableSpec":
        table_id = str(payload.get("id", "")).strip()
        title = str(payload.get("title", "")).strip()
        evidence_id = str(payload.get("evidence_id", "")).strip()
        if not _ID_PATTERN.fullmatch(table_id):
            raise PipelineError(f"Invalid table id: {table_id!r}")
        if not title or not evidence_id:
            raise PipelineError(f"Table {table_id!r} requires title and evidence_id.")
        columns_raw = payload.get("columns", [])
        if not isinstance(columns_raw, list) or not columns_raw:
            raise PipelineError(f"Table {table_id!r} requires at least one column.")
        return cls(
            table_id=table_id,
            title=title,
            evidence_id=evidence_id,
            columns=tuple(TableColumn.from_dict(item) for item in columns_raw),
            caption=str(payload.get("caption", "")).strip(),
        )


@dataclass(frozen=True, slots=True)
class RenderedTable:
    table_id: str
    markdown_path: Path
    csv_path: Path
    json_path: Path
    row_count: int
