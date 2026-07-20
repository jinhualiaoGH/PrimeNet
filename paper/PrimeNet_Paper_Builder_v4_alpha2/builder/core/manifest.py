from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .exceptions import ManifestError


@dataclass(frozen=True, slots=True)
class PaperManifest:
    name: str
    title: str
    version: str
    description: str
    required_evidence: tuple[str, ...]
    stages: tuple[str, ...]
    source_path: Path

    @classmethod
    def load(cls, path: Path) -> "PaperManifest":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ManifestError(f"Manifest not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise ManifestError(f"Invalid manifest JSON at {path}: {exc}") from exc

        if not isinstance(payload, dict):
            raise ManifestError("Manifest root must be a JSON object.")

        required = ("name", "title", "version")
        missing = [key for key in required if not payload.get(key)]
        if missing:
            raise ManifestError(f"Manifest missing required field(s): {', '.join(missing)}")

        evidence = _string_tuple(payload.get("required_evidence", []), "required_evidence")
        stages = _string_tuple(
            payload.get("stages", ["validate", "plan", "summarize"]),
            "stages",
        )

        return cls(
            name=str(payload["name"]),
            title=str(payload["title"]),
            version=str(payload["version"]),
            description=str(payload.get("description", "")),
            required_evidence=evidence,
            stages=stages,
            source_path=path.resolve(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "version": self.version,
            "description": self.description,
            "required_evidence": list(self.required_evidence),
            "stages": list(self.stages),
            "source_path": str(self.source_path),
        }


def _string_tuple(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ManifestError(f"{field} must be an array of strings")
    return tuple(value)
