from __future__ import annotations

from pathlib import Path


def test_pyproject_uses_explicit_builder_discovery() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.setuptools.packages.find]" in text
    assert 'include = ["builder", "builder.*"]' in text
