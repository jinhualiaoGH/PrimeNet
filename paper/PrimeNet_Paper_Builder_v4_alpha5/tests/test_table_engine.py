import json
from pathlib import Path

from builder.evidence import EvidenceLoader, EvidenceRegistry
from builder.tables import TableRenderer, TableSpec, TableSpecLoader


def test_table_spec_loader_discovers_architecture_table() -> None:
    project_root = Path(__file__).resolve().parents[1]
    specs = TableSpecLoader(project_root / "papers" / "architecture").discover()
    assert len(specs) == 1
    assert specs[0].table_id == "architecture.repository.overview"


def test_table_renderer_writes_three_formats(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    loader = EvidenceLoader(project_root / "evidence")
    registry = EvidenceRegistry.from_packages(loader.discover())
    spec = TableSpecLoader(project_root / "papers" / "architecture").discover()[0]
    result = TableRenderer(registry, loader).render(spec, tmp_path)
    assert result.row_count == 1
    assert result.markdown_path.exists()
    assert result.csv_path.exists()
    assert result.json_path.exists()
    payload = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert payload["rows"][0]["prime_count"] == 37_607_912_018


def test_table_spec_rejects_missing_columns() -> None:
    try:
        TableSpec.from_dict({"id": "x", "title": "X", "evidence_id": "e", "columns": []})
    except Exception as exc:
        assert "at least one column" in str(exc)
    else:
        raise AssertionError("Expected invalid specification to fail")
