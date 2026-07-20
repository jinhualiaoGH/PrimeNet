from __future__ import annotations

import json
from pathlib import Path

import pytest

from builder.cli.build_paper import main


def test_cli_version() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0


def test_cli_doctor(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    plugin = tmp_path / "papers" / "sample"
    plugin.mkdir(parents=True)
    (plugin / "paper.json").write_text(
        json.dumps({"name": "sample", "title": "Sample", "version": "1.0"}),
        encoding="utf-8",
    )
    (tmp_path / "evidence").mkdir()

    exit_code = main(["doctor", "--project-root", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "RESULT: READY" in captured.out
