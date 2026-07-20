from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .loader import EvidenceLoader
from .registry import EvidenceRegistry, RegisteredEvidence


@dataclass(frozen=True, slots=True)
class EvidenceIssue:
    severity: str
    evidence_id: str
    message: str


@dataclass(frozen=True, slots=True)
class EvidenceValidationReport:
    packages: int
    records: int
    issues: tuple[EvidenceIssue, ...]

    @property
    def passed(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def render(self) -> str:
        lines = [
            "PrimeNet Evidence Validation",
            "=" * 72,
            f"Packages: {self.packages}",
            f"Records:  {self.records}",
        ]
        for issue in self.issues:
            lines.append(f"[{issue.severity.upper()}] {issue.evidence_id}: {issue.message}")
        if not self.issues:
            lines.append("[PASS] All evidence records are valid.")
        lines.extend(["=" * 72, f"RESULT: {'READY' if self.passed else 'FAILED'}"])
        return "\n".join(lines)


class EvidenceValidator:
    def __init__(self, loader: EvidenceLoader) -> None:
        self.loader = loader

    def validate(self, registry: EvidenceRegistry) -> EvidenceValidationReport:
        issues: list[EvidenceIssue] = []
        for registered in registry.records():
            issues.extend(self._validate_record(registry, registered))
        return EvidenceValidationReport(
            packages=len(registry.packages()),
            records=len(registry.records()),
            issues=tuple(issues),
        )

    def _validate_record(
        self,
        registry: EvidenceRegistry,
        registered: RegisteredEvidence,
    ) -> list[EvidenceIssue]:
        record = registered.record
        issues: list[EvidenceIssue] = []
        path = self.loader.source_path(registered.package, record)
        if not path.is_file():
            issues.append(EvidenceIssue("error", record.evidence_id, f"source not found: {path}"))
            return issues
        if record.source.sha256:
            actual = self._sha256(path)
            if actual != record.source.sha256:
                issues.append(
                    EvidenceIssue(
                        "error",
                        record.evidence_id,
                        f"sha256 mismatch: expected {record.source.sha256}, found {actual}",
                    )
                )
        for dependency in record.depends_on:
            if not registry.contains(dependency):
                issues.append(
                    EvidenceIssue("error", record.evidence_id, f"missing dependency: {dependency}")
                )
        try:
            self.loader.load_payload(registered.package, record)
        except Exception as exc:  # normalized into validation report
            issues.append(EvidenceIssue("error", record.evidence_id, str(exc)))
        return issues

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
