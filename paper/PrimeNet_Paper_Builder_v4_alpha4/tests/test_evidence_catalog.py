import json
from pathlib import Path

from builder.evidence import EvidenceCatalog, EvidenceLoader, EvidenceRegistry


def test_catalog_writes_canonical_json(tmp_path: Path) -> None:
    root = Path(__file__).parents[1] / "evidence"
    loader = EvidenceLoader(root)
    registry = EvidenceRegistry.from_packages(loader.discover())
    output = EvidenceCatalog(registry, loader).write(tmp_path / "catalog.json")
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == "primenet.evidence.catalog/v1"
    assert payload["evidence_count"] >= 1
