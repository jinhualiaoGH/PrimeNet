from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .models import RenderedSection


class ManuscriptAssembler:
    @staticmethod
    def assemble(sections: Iterable[RenderedSection], destination: Path) -> Path:
        ordered = tuple(sorted(sections, key=lambda item: (item.order, item.section_id)))
        content = "\n\n".join(item.markdown_path.read_text(encoding="utf-8").strip() for item in ordered)
        destination.write_text(content + ("\n" if content else ""), encoding="utf-8")
        return destination
