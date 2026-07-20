from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import RenderedFigure


class FigureCatalog:
    @staticmethod
    def write(figures: Iterable[RenderedFigure], output_path: Path) -> Path:
        payload = {
            "figures": [
                {
                    "id": item.figure_id,
                    "point_count": item.point_count,
                    "png": str(item.png_path),
                    "svg": str(item.svg_path),
                    "metadata": str(item.metadata_path),
                }
                for item in figures
            ]
        }
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return output_path
