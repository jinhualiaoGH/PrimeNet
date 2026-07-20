from __future__ import annotations

import json
from pathlib import Path

from builder.core.configuration import PaperConfiguration
from builder.core.doctor import Doctor


def test_doctor_reports_ready_for_valid_project(tmp_path: Path) -> None:
    plugin = tmp_path / "papers" / "sample"
    plugin.mkdir(parents=True)
    (plugin / "paper.json").write_text(
        json.dumps({"name": "sample", "title": "Sample", "version": "1.0"}),
        encoding="utf-8",
    )
    (tmp_path / "evidence").mkdir()

    report = Doctor(PaperConfiguration.defaults(tmp_path)).run()

    assert report.passed
    assert "RESULT: READY" in report.render()
    assert any(check.name == "Paper plugins" for check in report.checks)
