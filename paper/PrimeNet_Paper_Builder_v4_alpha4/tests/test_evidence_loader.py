import json
from pathlib import Path

from builder.evidence import EvidenceLoader


def test_loader_discovers_and_loads_json(tmp_path: Path) -> None:
    package = tmp_path / "demo"
    package.mkdir()
    (package / "value.json").write_text('{"value": 7}', encoding="utf-8")
    (package / "package.json").write_text(
        json.dumps(
            {
                "package_id": "demo",
                "version": "1.0.0",
                "evidence": [
                    {
                        "id": "demo.value",
                        "kind": "metric",
                        "title": "Value",
                        "version": "1.0.0",
                        "source": {"path": "value.json", "media_type": "application/json"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    loader = EvidenceLoader(tmp_path)
    packages = loader.discover()
    assert len(packages) == 1
    assert loader.load_payload(packages[0], packages[0].records[0]) == {"value": 7}
