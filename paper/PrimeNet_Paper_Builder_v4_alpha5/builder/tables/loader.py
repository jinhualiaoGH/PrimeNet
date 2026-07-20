from __future__ import annotations

import json
from pathlib import Path

from builder.core.exceptions import PipelineError

from .models import TableSpec


class TableSpecLoader:
    def __init__(self, plugin_root: Path) -> None:
        self.plugin_root = plugin_root.resolve()

    def discover(self) -> tuple[TableSpec, ...]:
        table_root = self.plugin_root / "tables"
        if not table_root.exists():
            return ()
        specs: list[TableSpec] = []
        for path in sorted(table_root.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise PipelineError(f"Cannot read table specification {path}: {exc}") from exc
            if not isinstance(payload, dict):
                raise PipelineError(f"Table specification must be a JSON object: {path}")
            specs.append(TableSpec.from_dict(payload))
        ids = [item.table_id for item in specs]
        if len(ids) != len(set(ids)):
            raise PipelineError("Duplicate table IDs were discovered.")
        return tuple(specs)
