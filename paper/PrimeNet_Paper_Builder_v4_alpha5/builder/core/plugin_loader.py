from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .exceptions import PluginNotFoundError
from .manifest import PaperManifest


@dataclass(frozen=True, slots=True)
class PaperPlugin:
    root: Path
    manifest: PaperManifest


class PluginLoader:
    def __init__(self, papers_root: Path) -> None:
        self.papers_root = papers_root.resolve()

    def discover(self) -> dict[str, PaperPlugin]:
        plugins: dict[str, PaperPlugin] = {}
        if not self.papers_root.exists():
            return plugins

        for manifest_path in sorted(self.papers_root.glob("*/paper.json")):
            manifest = PaperManifest.load(manifest_path)
            if manifest.name in plugins:
                raise PluginNotFoundError(
                    f"Duplicate paper plugin name: {manifest.name}"
                )
            plugins[manifest.name] = PaperPlugin(
                root=manifest_path.parent.resolve(),
                manifest=manifest,
            )
        return plugins

    def load(self, name: str) -> PaperPlugin:
        plugins = self.discover()
        try:
            return plugins[name]
        except KeyError as exc:
            available = ", ".join(sorted(plugins)) or "none"
            raise PluginNotFoundError(
                f"Paper plugin '{name}' not found. Available: {available}"
            ) from exc
