import json
from pathlib import Path

from builder.core.configuration import PaperConfiguration
from builder.core.pipeline import BuildPipeline
from builder.core.plugin_loader import PluginLoader


def test_foundation_pipeline(tmp_path: Path) -> None:
    plugin_root = tmp_path / "papers" / "architecture"
    plugin_root.mkdir(parents=True)
    (plugin_root / "paper.json").write_text(
        json.dumps(
            {
                "name": "architecture",
                "title": "Architecture",
                "version": "0.1",
                "required_evidence": [],
                "stages": ["validate", "plan", "summarize"],
            }
        ),
        encoding="utf-8",
    )
    cfg = PaperConfiguration.defaults(tmp_path).with_overrides(paper="architecture")
    cfg.ensure_runtime_directories()
    plugin = PluginLoader(cfg.papers_root).load("architecture")
    pipeline = BuildPipeline()
    context = pipeline.create_context(cfg, plugin)
    result = pipeline.run(context)
    assert result.summary_path.exists()
    assert (context.build_dir / "FOUNDATION_READY.txt").exists()
