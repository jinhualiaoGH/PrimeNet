import json
from pathlib import Path

from builder.core.plugin_loader import PluginLoader


def test_discovers_plugin(tmp_path: Path) -> None:
    plugin = tmp_path / "papers" / "sample"
    plugin.mkdir(parents=True)
    (plugin / "paper.json").write_text(
        json.dumps({"name": "sample", "title": "Sample", "version": "1.0"}),
        encoding="utf-8",
    )
    found = PluginLoader(tmp_path / "papers").discover()
    assert list(found) == ["sample"]
