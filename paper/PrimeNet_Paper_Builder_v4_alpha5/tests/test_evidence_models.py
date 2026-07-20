import pytest

from builder.core.exceptions import EvidenceError
from builder.evidence.models import EvidenceKind, EvidenceRecord


def test_record_from_dict() -> None:
    record = EvidenceRecord.from_dict(
        {
            "id": "paper.metric.count",
            "kind": "metric",
            "title": "Count",
            "version": "1.0.0",
            "source": {"path": "count.json", "media_type": "application/json"},
        }
    )
    assert record.kind is EvidenceKind.METRIC
    assert record.evidence_id == "paper.metric.count"


def test_record_rejects_invalid_id() -> None:
    with pytest.raises(EvidenceError):
        EvidenceRecord.from_dict(
            {
                "id": "Bad ID",
                "kind": "metric",
                "title": "Count",
                "version": "1.0.0",
                "source": {"path": "count.json", "media_type": "application/json"},
            }
        )
