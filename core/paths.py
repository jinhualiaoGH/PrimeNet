"""
PrimeNet Path Service

Responsible for filesystem path management.

Design principles
-----------------
- Never reads YAML directly.
- Uses the shared Configuration object.
- Creates runtime directories when needed.
- Provides utility functions for filesystem operations.
"""

from __future__ import annotations

from pathlib import Path
import shutil

from core.config import Configuration


class Paths:
    """
    PrimeNet filesystem service.
    """

    def __init__(self, config: Configuration):

        self.config = config

    # ---------------------------------------------------------
    # Core paths
    # ---------------------------------------------------------

    @property
    def project_root(self) -> Path:
        return self.config.project_root

    @property
    def repository(self) -> Path:
        return self.config.repository_path

    @property
    def catalog(self) -> Path:
        return self.config.catalog_path

    @property
    def core(self) -> Path:
        return self.config.core_path

    @property
    def observatories(self) -> Path:
        return self.config.observatories_path

    @property
    def atlases(self) -> Path:
        return self.config.atlases_path

    @property
    def papers(self) -> Path:
        return self.config.papers_path

    @property
    def releases(self) -> Path:
        return self.config.releases_path

    @property
    def results(self) -> Path:
        return self.config.results_path

    @property
    def figures(self) -> Path:
        return self.config.figures_path

    @property
    def docs(self) -> Path:
        return self.config.docs_path

    @property
    def logs(self) -> Path:
        return self.config.logs_path

    @property
    def tmp(self) -> Path:
        return self.config.tmp_path

    @property
    def cache(self) -> Path:
        return self.config.cache_path

    @property
    def database(self) -> Path:
        return self.config.catalog_database

    # ---------------------------------------------------------
    # Directory management
    # ---------------------------------------------------------

    def ensure_directory(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    def ensure_runtime_directories(self) -> None:

        directories = [
            self.logs,
            self.results,
            self.figures,
            self.tmp,
            self.cache,
        ]

        for d in directories:
            self.ensure_directory(d)

    # ---------------------------------------------------------
    # Temporary directory
    # ---------------------------------------------------------

    def clean_tmp(self) -> None:

        if self.tmp.exists():

            shutil.rmtree(self.tmp)

        self.tmp.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------
    # Dynamic builders
    # ---------------------------------------------------------

    def release_directory(self, version: str) -> Path:

        path = self.releases / version

        path.mkdir(parents=True, exist_ok=True)

        return path

    def atlas_directory(self, name: str) -> Path:

        path = self.atlases / name

        path.mkdir(parents=True, exist_ok=True)

        return path

    def paper_directory(self, name: str) -> Path:

        path = self.papers / name

        path.mkdir(parents=True, exist_ok=True)

        return path

    def figure_directory(self, name: str) -> Path:

        path = self.figures / name

        path.mkdir(parents=True, exist_ok=True)

        return path

    # ---------------------------------------------------------
    # Diagnostics
    # ---------------------------------------------------------

    def summary(self) -> None:

        print("=" * 80)
        print("PrimeNet Path Service")
        print("=" * 80)

        print("Project :", self.project_root)
        print("Repository :", self.repository)
        print("Catalog :", self.catalog)
        print("Database :", self.database)
        print("Results :", self.results)
        print("Figures :", self.figures)
        print("Logs :", self.logs)
        print("Temp :", self.tmp)
        print("Cache :", self.cache)

        print("=" * 80)


def main():

    cfg = Configuration()

    paths = Paths(cfg)

    paths.ensure_runtime_directories()

    paths.summary()


if __name__ == "__main__":

    main()