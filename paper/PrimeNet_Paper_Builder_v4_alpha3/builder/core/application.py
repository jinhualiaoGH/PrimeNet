from __future__ import annotations

import logging
from dataclasses import dataclass

from .configuration import PaperConfiguration
from .logging import configure_logging
from .pipeline import BuildPipeline, BuildResult
from .plugin_loader import PluginLoader

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class PaperBuilderApplication:
    configuration: PaperConfiguration

    def list_papers(self) -> dict[str, str]:
        loader = PluginLoader(self.configuration.papers_root)
        return {
            name: plugin.manifest.title
            for name, plugin in loader.discover().items()
        }

    def build(self) -> BuildResult:
        if self.configuration.paper is None:
            raise ValueError("A paper name is required for build execution.")

        self.configuration.ensure_runtime_directories()
        log_path = configure_logging(
            self.configuration.log_root,
            verbose=self.configuration.verbose,
        )
        LOGGER.info("PrimeNet Paper Builder starting")
        LOGGER.info("Log file: %s", log_path)

        loader = PluginLoader(self.configuration.papers_root)
        plugin = loader.load(self.configuration.paper)
        pipeline = BuildPipeline()
        context = pipeline.create_context(self.configuration, plugin)
        result = pipeline.run(context)
        LOGGER.info("Build complete: %s", result.summary_path)
        return result
