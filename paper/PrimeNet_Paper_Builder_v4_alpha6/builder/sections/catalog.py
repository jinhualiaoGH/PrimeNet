from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import RenderedSection


class SectionCatalog:
    @staticmethod
    def write(sections: Iterable[RenderedSection], output_path: Path) -> Path:
        ordered = tuple(sorted(sections, key=lambda item: (item.order, item.section_id)))
        payload = {
            "section_count": len(ordered),
            "sections": [
                {
                    "id": item.section_id,
                    "order": item.order,
                    "markdown": str(item.markdown_path),
                    "unresolved_count": item.unresolved_count,
                }
                for item in ordered
            ],
        }
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return output_path
