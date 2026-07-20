from __future__ import annotations

from pathlib import Path

_FALLBACK_VERSION = "4.0.0-alpha.2"


def _read_version() -> str:
    version_file = Path(__file__).resolve().parents[2] / "VERSION"
    try:
        value = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return _FALLBACK_VERSION
    return value or _FALLBACK_VERSION


__version__ = _read_version()
