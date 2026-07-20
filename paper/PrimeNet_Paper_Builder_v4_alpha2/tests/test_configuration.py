from pathlib import Path

from builder.core.configuration import PaperConfiguration


def test_defaults_are_rooted(tmp_path: Path) -> None:
    cfg = PaperConfiguration.defaults(tmp_path)
    assert cfg.project_root == tmp_path.resolve()
    assert cfg.papers_root == tmp_path.resolve() / "papers"
    assert cfg.release == "preview"
