from pathlib import Path

import pytest

from builder.core.exceptions import EvidenceError
from builder.evidence.models import EvidencePackage, EvidenceRecord
from builder.evidence.registry import EvidenceRegistry


def record(evidence_id: str) -> EvidenceRecord:
    return EvidenceRecord.from_dict(
        {
            "id": evidence_id,
            "kind": "text",
            "title": evidence_id,
            "version": "1",
            "source": {"path": "a.txt", "media_type": "text/plain"},
        }
    )


def test_registry_lookup() -> None:
    package = EvidencePackage("demo", "1", "", Path.cwd(), (record("demo.a"),))
    registry = EvidenceRegistry.from_packages((package,))
    assert registry.contains("demo.a")
    assert registry.get("demo.a").record.title == "demo.a"


def test_registry_rejects_duplicate_ids() -> None:
    one = EvidencePackage("one", "1", "", Path.cwd(), (record("demo.a"),))
    two = EvidencePackage("two", "1", "", Path.cwd(), (record("demo.a"),))
    with pytest.raises(EvidenceError):
        EvidenceRegistry.from_packages((one, two))
