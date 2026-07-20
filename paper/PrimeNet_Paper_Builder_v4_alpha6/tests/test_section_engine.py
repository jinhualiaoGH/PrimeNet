from __future__ import annotations

import json
from pathlib import Path

import pytest

from builder.core.exceptions import PipelineError
from builder.evidence import EvidenceLoader, EvidenceRegistry
from builder.sections import ManuscriptAssembler, SectionCatalog, SectionRenderer, SectionSpec, SectionSpecLoader


def _project(tmp_path: Path) -> tuple[Path, EvidenceLoader, EvidenceRegistry, Path]:
    evidence_root = tmp_path / "evidence"
    package = evidence_root / "baseline"
    package.mkdir(parents=True)
    (package / "data.json").write_text(json.dumps({"count": 1234}), encoding="utf-8")
    (package / "package.json").write_text(json.dumps({
        "package_id": "baseline",
        "version": "1",
        "description": "test",
        "evidence": [{
            "id": "test.metric",
            "kind": "metric",
            "title": "Metric",
            "version": "1",
            "source": {"path": "data.json", "media_type": "application/json"}
        }]
    }), encoding="utf-8")
    plugin = tmp_path / "paper"
    (plugin / "sections").mkdir(parents=True)
    build = tmp_path / "build"
    (build / "tables").mkdir(parents=True)
    (build / "figures").mkdir(parents=True)
    (build / "tables" / "test.table.md").write_text("| A |\n|---|\n| 1 |\n", encoding="utf-8")
    (build / "figures" / "test.figure.png").write_bytes(b"png")
    (build / "figures" / "test.figure.json").write_text(json.dumps({"caption": "A figure"}), encoding="utf-8")
    loader = EvidenceLoader(evidence_root)
    registry = EvidenceRegistry.from_packages(loader.discover())
    return plugin, loader, registry, build


def test_section_spec_validation() -> None:
    spec = SectionSpec.from_dict({"id": "intro", "title": "Intro", "order": 1, "template": "sections/a.md"})
    assert spec.level == 1
    with pytest.raises(PipelineError):
        SectionSpec.from_dict({"id": "Bad ID", "title": "Intro", "template": "a.md"})


def test_loader_orders_sections(tmp_path: Path) -> None:
    plugin, *_ = _project(tmp_path)
    for name, order in (("b", 20), ("a", 10)):
        (plugin / "sections" / f"{name}.md").write_text("body", encoding="utf-8")
        (plugin / "sections" / f"{name}.json").write_text(json.dumps({
            "id": name, "title": name.upper(), "order": order, "template": f"sections/{name}.md"
        }), encoding="utf-8")
    assert [item.section_id for item in SectionSpecLoader(plugin).discover()] == ["a", "b"]


def test_renderer_resolves_evidence_table_and_figure(tmp_path: Path) -> None:
    plugin, loader, registry, build = _project(tmp_path)
    template = plugin / "sections" / "intro.md"
    template.write_text(
        "Count: {{evidence:test.metric|count}}\n\n{{table:test.table}}\n\n{{figure:test.figure}}",
        encoding="utf-8",
    )
    spec = SectionSpec("intro", "Introduction", 1, "sections/intro.md")
    rendered = SectionRenderer(registry, loader, plugin, build).render(spec, build / "sections")
    text = rendered.markdown_path.read_text(encoding="utf-8")
    assert "Count: 1,234" in text
    assert "| A |" in text
    assert "![A figure](../figures/test.figure.png)" in text
    assert rendered.unresolved_count == 0


def test_catalog_and_manuscript_are_deterministic(tmp_path: Path) -> None:
    plugin, loader, registry, build = _project(tmp_path)
    rendered = []
    for section_id, order in (("later", 20), ("earlier", 10)):
        path = plugin / "sections" / f"{section_id}.md"
        path.write_text(section_id, encoding="utf-8")
        spec = SectionSpec(section_id, section_id.title(), order, f"sections/{section_id}.md")
        rendered.append(SectionRenderer(registry, loader, plugin, build).render(spec, build / "sections"))
    catalog = SectionCatalog.write(rendered, build / "section_catalog.json")
    manuscript = ManuscriptAssembler.assemble(rendered, build / "manuscript.md")
    payload = json.loads(catalog.read_text(encoding="utf-8"))
    assert [item["id"] for item in payload["sections"]] == ["earlier", "later"]
    assert manuscript.read_text(encoding="utf-8").index("Earlier") < manuscript.read_text(encoding="utf-8").index("Later")
