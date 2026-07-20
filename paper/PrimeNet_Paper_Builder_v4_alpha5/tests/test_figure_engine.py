from __future__ import annotations

import json
from pathlib import Path

import pytest

from builder.core.exceptions import PipelineError
from builder.evidence import EvidenceLoader, EvidenceRegistry
from builder.figures import FigureRenderer, FigureSpec, FigureSpecLoader


def test_figure_spec_validation() -> None:
    spec = FigureSpec.from_dict(
        {
            "id": "test.figure",
            "title": "Test",
            "evidence_id": "test.evidence",
            "kind": "bar",
            "series": [{"key": "value", "label": "Value"}],
        }
    )
    assert spec.figure_id == "test.figure"
    assert spec.series[0].key == "value"


def test_figure_spec_rejects_empty_series() -> None:
    with pytest.raises(PipelineError):
        FigureSpec.from_dict(
            {"id": "test.figure", "title": "Test", "evidence_id": "test.evidence", "series": []}
        )


def test_architecture_figure_render(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    loader = EvidenceLoader(project_root / "evidence")
    registry = EvidenceRegistry.from_packages(loader.discover())
    specs = FigureSpecLoader(project_root / "papers" / "architecture").discover()
    assert len(specs) == 1
    rendered = FigureRenderer(registry, loader).render(specs[0], tmp_path)
    assert rendered.png_path.exists()
    assert rendered.png_path.stat().st_size > 0
    assert rendered.svg_path.exists()
    metadata = json.loads(rendered.metadata_path.read_text(encoding="utf-8"))
    assert metadata["evidence_id"] == "architecture.repository.summary_1t"
    assert metadata["values"] == [1000000000000.0, 37607912018.0, 100.0]
