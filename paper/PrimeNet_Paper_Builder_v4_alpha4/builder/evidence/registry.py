from __future__ import annotations

from dataclasses import dataclass

from builder.core.exceptions import EvidenceError

from .models import EvidencePackage, EvidenceRecord


@dataclass(frozen=True, slots=True)
class RegisteredEvidence:
    package: EvidencePackage
    record: EvidenceRecord


class EvidenceRegistry:
    def __init__(self) -> None:
        self._packages: dict[str, EvidencePackage] = {}
        self._records: dict[str, RegisteredEvidence] = {}

    @classmethod
    def from_packages(cls, packages: tuple[EvidencePackage, ...]) -> "EvidenceRegistry":
        registry = cls()
        for package in packages:
            registry.register_package(package)
        return registry

    def register_package(self, package: EvidencePackage) -> None:
        if package.package_id in self._packages:
            raise EvidenceError(f"Duplicate evidence package id: {package.package_id}")
        pending_ids = [record.evidence_id for record in package.records]
        duplicates = {item for item in pending_ids if pending_ids.count(item) > 1}
        if duplicates:
            raise EvidenceError("Duplicate evidence ids in package: " + ", ".join(sorted(duplicates)))
        conflicts = sorted(set(pending_ids).intersection(self._records))
        if conflicts:
            raise EvidenceError("Evidence ids already registered: " + ", ".join(conflicts))
        self._packages[package.package_id] = package
        for record in package.records:
            self._records[record.evidence_id] = RegisteredEvidence(package, record)

    def get(self, evidence_id: str) -> RegisteredEvidence:
        try:
            return self._records[evidence_id]
        except KeyError as exc:
            raise EvidenceError(f"Unknown evidence id: {evidence_id}") from exc

    def contains(self, evidence_id: str) -> bool:
        return evidence_id in self._records

    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._records))

    def packages(self) -> tuple[EvidencePackage, ...]:
        return tuple(self._packages[key] for key in sorted(self._packages))

    def records(self) -> tuple[RegisteredEvidence, ...]:
        return tuple(self._records[key] for key in sorted(self._records))
