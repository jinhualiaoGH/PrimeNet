from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import RenderedTable


class TableCatalog:
    @staticmethod
    def write(tables: tuple[RenderedTable, ...], destination: Path) -> Path:
        payload = {
            "table_count": len(tables),
            "tables": [
                {
                    **asdict(item),
                    "markdown_path": str(item.markdown_path),
                    "csv_path": str(item.csv_path),
                    "json_path": str(item.json_path),
                }
                for item in tables
            ],
        }
        destination.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return destination
