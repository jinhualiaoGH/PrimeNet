from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from builder.core.exceptions import EvidenceError

_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class EvidenceKind(str, Enum):
    METRIC = "metric"
    TABLE = "table"
    FIGURE = "figure"
    TEXT = "text"
    DATASET = "dataset"


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    path: str
    media_type: str
    sha256: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EvidenceSource":
        path = str(payload.get("path", "")).strip()
        media_type = str(payload.get("media_type", "")).strip()
        sha256 = payload.get("sha256")
        if not path:
            raise EvidenceError("Evidence source path is required.")
        if Path(path).is_absolute():
            raise EvidenceError("Evidence source paths must be package-relative.")
        if not media_type:
            raise EvidenceError("Evidence source media_type is required.")
        if sha256 is not None:
            sha256 = str(sha256).lower().strip()
            if not re.fullmatch(r"[0-9a-f]{64}", sha256):
                raise EvidenceError("Evidence source sha256 must contain 64 hex characters.")
        return cls(path=path, media_type=media_type, sha256=sha256)


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: str
    kind: EvidenceKind
    title: str
    version: str
    source: EvidenceSource
    description: str = ""
    depends_on: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EvidenceRecord":
        evidence_id = str(payload.get("id", "")).strip()
        title = str(payload.get("title", "")).strip()
        version = str(payload.get("version", "")).strip()
        if not _ID_PATTERN.fullmatch(evidence_id):
            raise EvidenceError(
                f"Invalid evidence id {evidence_id!r}; use lowercase letters, numbers, dots, underscores, or hyphens."
            )
        if not title:
            raise EvidenceError(f"Evidence {evidence_id!r} requires a title.")
        if not version:
            raise EvidenceError(f"Evidence {evidence_id!r} requires a version.")
        try:
            kind = EvidenceKind(str(payload.get("kind", "")))
        except ValueError as exc:
            allowed = ", ".join(item.value for item in EvidenceKind)
            raise EvidenceError(f"Evidence {evidence_id!r} kind must be one of: {allowed}") from exc
        source_payload = payload.get("source")
        if not isinstance(source_payload, Mapping):
            raise EvidenceError(f"Evidence {evidence_id!r} requires a source object.")
        depends_raw = payload.get("depends_on", [])
        if not isinstance(depends_raw, list) or not all(isinstance(item, str) for item in depends_raw):
            raise EvidenceError(f"Evidence {evidence_id!r} depends_on must be a string list.")
        metadata = payload.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise EvidenceError(f"Evidence {evidence_id!r} metadata must be an object.")
        return cls(
            evidence_id=evidence_id,
            kind=kind,
            title=title,
            version=version,
            source=EvidenceSource.from_dict(source_payload),
            description=str(payload.get("description", "")).strip(),
            depends_on=tuple(depends_raw),
            metadata=dict(metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = payload.pop("evidence_id")
        payload["kind"] = self.kind.value
        return payload


@dataclass(frozen=True, slots=True)
class EvidencePackage:
    package_id: str
    version: str
    description: str
    root: Path
    records: tuple[EvidenceRecord, ...]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any], *, root: Path) -> "EvidencePackage":
        package_id = str(payload.get("package_id", "")).strip()
        version = str(payload.get("version", "")).strip()
        if not _ID_PATTERN.fullmatch(package_id):
            raise EvidenceError(f"Invalid evidence package id: {package_id!r}")
        if not version:
            raise EvidenceError(f"Evidence package {package_id!r} requires a version.")
        records_raw = payload.get("evidence", [])
        if not isinstance(records_raw, list):
            raise EvidenceError(f"Evidence package {package_id!r} evidence must be a list.")
        records = tuple(EvidenceRecord.from_dict(item) for item in records_raw)
        return cls(
            package_id=package_id,
            version=version,
            description=str(payload.get("description", "")).strip(),
            root=root.resolve(),
            records=records,
        )
