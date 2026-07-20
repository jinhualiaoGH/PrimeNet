from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from builder.core.exceptions import EvidenceError

from .models import EvidencePackage, EvidenceRecord


class EvidenceLoader:
    MANIFEST_NAME = "package.json"

    def __init__(self, evidence_root: Path) -> None:
        self.evidence_root = evidence_root.resolve()

    def discover(self) -> tuple[EvidencePackage, ...]:
        if not self.evidence_root.exists():
            return ()
        packages = [self.load_package(path) for path in sorted(self.evidence_root.glob(f"*/{self.MANIFEST_NAME}"))]
        return tuple(packages)

    def load_package(self, manifest_path: Path) -> EvidencePackage:
        manifest_path = manifest_path.resolve()
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise EvidenceError(f"Evidence package manifest not found: {manifest_path}") from exc
        except json.JSONDecodeError as exc:
            raise EvidenceError(f"Invalid evidence package JSON at {manifest_path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise EvidenceError(f"Evidence package root must be an object: {manifest_path}")
        return EvidencePackage.from_dict(payload, root=manifest_path.parent)

    @staticmethod
    def source_path(package: EvidencePackage, record: EvidenceRecord) -> Path:
        candidate = (package.root / record.source.path).resolve()
        try:
            candidate.relative_to(package.root)
        except ValueError as exc:
            raise EvidenceError(
                f"Evidence source escapes package root: {record.evidence_id} -> {record.source.path}"
            ) from exc
        return candidate

    def load_payload(self, package: EvidencePackage, record: EvidenceRecord) -> Any:
        path = self.source_path(package, record)
        media_type = record.source.media_type.lower()
        try:
            if media_type in {"application/json", "text/json"}:
                return json.loads(path.read_text(encoding="utf-8"))
            if media_type == "text/csv":
                with path.open("r", encoding="utf-8", newline="") as stream:
                    return list(csv.DictReader(stream))
            if media_type.startswith("text/"):
                return path.read_text(encoding="utf-8")
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise EvidenceError(f"Evidence source not found: {path}") from exc
        except (OSError, json.JSONDecodeError, csv.Error) as exc:
            raise EvidenceError(f"Unable to load evidence source {path}: {exc}") from exc
