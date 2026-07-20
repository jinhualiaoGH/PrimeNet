from __future__ import annotations

import json
from pathlib import Path

from builder.core.exceptions import PipelineError

from .models import FigureSpec


class FigureSpecLoader:
    def __init__(self, plugin_root: Path) -> None:
        self.plugin_root = plugin_root.resolve()

    def discover(self) -> tuple[FigureSpec, ...]:
        root = self.plugin_root / "figures"
        if not root.exists():
            return ()
        return tuple(self.load(path) for path in sorted(root.glob("*.json")))

    @staticmethod
    def load(path: Path) -> FigureSpec:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise PipelineError(f"Figure specification not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise PipelineError(f"Invalid figure specification JSON at {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise PipelineError(f"Figure specification root must be an object: {path}")
        return FigureSpec.from_dict(payload)
