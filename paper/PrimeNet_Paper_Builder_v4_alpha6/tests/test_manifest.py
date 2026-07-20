import json
from pathlib import Path

from builder.core.manifest import PaperManifest


def test_manifest_load(tmp_path: Path) -> None:
    path = tmp_path / "paper.json"
    path.write_text(
        json.dumps({"name": "x", "title": "X", "version": "1.0"}),
        encoding="utf-8",
    )
    manifest = PaperManifest.load(path)
    assert manifest.name == "x"
    assert manifest.stages == ("validate", "plan", "summarize")
