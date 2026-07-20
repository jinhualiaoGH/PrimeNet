from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .exceptions import ConfigurationError


@dataclass(frozen=True, slots=True)
class PaperConfiguration:
    project_root: Path
    papers_root: Path
    evidence_root: Path
    output_root: Path
    release_root: Path
    log_root: Path
    paper: str | None = None
    release: str = "preview"
    strict: bool = True
    verbose: bool = False

    @classmethod
    def defaults(cls, project_root: Path | None = None) -> "PaperConfiguration":
        root = (project_root or Path.cwd()).resolve()
        return cls(
            project_root=root,
            papers_root=root / "papers",
            evidence_root=root / "evidence",
            output_root=root / "build",
            release_root=root / "releases",
            log_root=root / "logs",
        )

    @classmethod
    def from_json(
        cls,
        path: Path,
        *,
        project_root: Path | None = None,
    ) -> "PaperConfiguration":
        path = path.resolve()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ConfigurationError(f"Configuration file not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise ConfigurationError(
                f"Invalid JSON configuration at {path}: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise ConfigurationError("Configuration root must be a JSON object.")

        root = (project_root or path.parent).resolve()
        cfg = cls.defaults(root)
        updates: dict[str, Any] = {}
        path_fields = {
            "papers_root",
            "evidence_root",
            "output_root",
            "release_root",
            "log_root",
        }

        for key, value in payload.items():
            if not hasattr(cfg, key):
                raise ConfigurationError(f"Unknown configuration key: {key}")
            if key in path_fields:
                candidate = Path(str(value))
                updates[key] = candidate if candidate.is_absolute() else root / candidate
            else:
                updates[key] = value

        result = replace(cfg, **updates)
        result.validate()
        return result

    def with_overrides(self, **overrides: Any) -> "PaperConfiguration":
        clean = {key: value for key, value in overrides.items() if value is not None}
        result = replace(self, **clean)
        result.validate()
        return result

    def validate(self) -> None:
        if self.release not in {"preview", "candidate", "final"}:
            raise ConfigurationError(
                "release must be one of: preview, candidate, final"
            )
        if self.paper is not None and not self.paper.strip():
            raise ConfigurationError("paper cannot be blank")

    def ensure_runtime_directories(self) -> None:
        for path in (self.output_root, self.release_root, self.log_root):
            path.mkdir(parents=True, exist_ok=True)
