from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from builder.core.version import __version__

from .loader import EvidenceLoader
from .registry import EvidenceRegistry


@dataclass(frozen=True, slots=True)
class EvidenceCatalog:
    registry: EvidenceRegistry
    loader: EvidenceLoader

    def to_dict(self) -> dict[str, Any]:
        packages = []
        for package in self.registry.packages():
            packages.append(
                {
                    "package_id": package.package_id,
                    "version": package.version,
                    "description": package.description,
                    "root": str(package.root),
                    "evidence": [record.to_dict() for record in package.records],
                }
            )
        return {
            "schema": "primenet.evidence.catalog/v1",
            "builder_version": __version__,
            "package_count": len(packages),
            "evidence_count": len(self.registry.records()),
            "packages": packages,
        }

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return path
