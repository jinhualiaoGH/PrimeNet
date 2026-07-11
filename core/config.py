"""
PrimeNet Core Configuration Service

This module provides the shared Configuration object for PrimeNet.

Design rule:
    No PrimeNet component should hard-code project paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import sys


class ConfigurationError(Exception):
    """Raised when PrimeNet configuration is invalid."""


class Configuration:
    """
    Shared PrimeNet configuration service.
    """

    def __init__(self, project_root: Path | None = None):

        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent

        self.project_root = project_root
        self.config_file = self.project_root / "config" / "primenet.yaml"

        if not self.config_file.exists():
            raise ConfigurationError(
                f"PrimeNet configuration file not found:\n{self.config_file}"
            )

        self._cfg = self._load_yaml(self.config_file)
        self._validate()

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        try:
            import yaml
        except ImportError as exc:
            raise ConfigurationError(
                "PyYAML is required to read primenet.yaml.\n"
                "Install it with:\n\n"
                "    py -m pip install pyyaml\n"
            ) from exc

        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ConfigurationError(
                f"Configuration file is empty or invalid:\n{path}"
            )

        return data

    def _get(self, *keys: str, default: Any = None) -> Any:
        current = self._cfg

        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]

        return current

    def _require(self, *keys: str) -> Any:
        value = self._get(*keys)

        if value is None:
            joined = ".".join(keys)
            raise ConfigurationError(
                f"Missing required configuration field: {joined}"
            )

        return value

    def _resolve_path(self, value: str | Path) -> Path:
        path = Path(value)

        if path.is_absolute():
            return path

        return self.project_root / path

    def _validate(self) -> None:
        required_sections = [
            "project",
            "paths",
            "database",
            "repository",
            "runtime",
            "logging",
            "observatories",
            "products",
            "metadata",
        ]

        for section in required_sections:
            if section not in self._cfg:
                raise ConfigurationError(
                    f"Missing required configuration section: {section}"
                )

        self._require("project", "name")
        self._require("project", "version")
        self._require("paths", "repository")
        self._require("paths", "catalog")
        self._require("database", "catalog")

    # ------------------------------------------------------------------
    # Project
    # ------------------------------------------------------------------

    @property
    def project_id(self) -> str:
        return str(self._get("project", "id", default="PRIMENET"))

    @property
    def project_name(self) -> str:
        return str(self._require("project", "name"))

    @property
    def project_version(self) -> str:
        return str(self._require("project", "version"))

    @property
    def project_description(self) -> str:
        return str(self._get("project", "description", default=""))

    # ------------------------------------------------------------------
    # Resolved paths
    # ------------------------------------------------------------------

    @property
    def repository_path(self) -> Path:
        return self._resolve_path(self._require("paths", "repository"))

    @property
    def catalog_path(self) -> Path:
        return self._resolve_path(self._require("paths", "catalog"))

    @property
    def core_path(self) -> Path:
        return self._resolve_path(self._get("paths", "core", default="core"))

    @property
    def observatories_path(self) -> Path:
        return self._resolve_path(
            self._get("paths", "observatories", default="observatories")
        )

    @property
    def atlases_path(self) -> Path:
        return self._resolve_path(self._get("paths", "atlases", default="atlases"))

    @property
    def papers_path(self) -> Path:
        return self._resolve_path(self._get("paths", "papers", default="papers"))

    @property
    def releases_path(self) -> Path:
        return self._resolve_path(
            self._get("paths", "releases", default="releases")
        )

    @property
    def figures_path(self) -> Path:
        return self._resolve_path(self._get("paths", "figures", default="figures"))

    @property
    def results_path(self) -> Path:
        return self._resolve_path(self._get("paths", "results", default="results"))

    @property
    def logs_path(self) -> Path:
        return self._resolve_path(self._get("paths", "logs", default="logs"))

    @property
    def docs_path(self) -> Path:
        return self._resolve_path(self._get("paths", "docs", default="docs"))

    @property
    def scripts_path(self) -> Path:
        return self._resolve_path(self._get("paths", "scripts", default="scripts"))

    @property
    def tmp_path(self) -> Path:
        return self._resolve_path(
            self._get("runtime", "temporary_directory", default="tmp")
        )

    @property
    def cache_path(self) -> Path:
        return self._resolve_path(
            self._get("runtime", "cache_directory", default="cache")
        )

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    @property
    def catalog_database(self) -> Path:
        return self._resolve_path(self._require("database", "catalog"))

    # ------------------------------------------------------------------
    # Raw sections
    # ------------------------------------------------------------------

    @property
    def repository(self) -> dict[str, Any]:
        return dict(self._get("repository", default={}))

    @property
    def runtime(self) -> dict[str, Any]:
        return dict(self._get("runtime", default={}))

    @property
    def logging(self) -> dict[str, Any]:
        return dict(self._get("logging", default={}))

    @property
    def observatories(self) -> dict[str, Any]:
        return dict(self._get("observatories", default={}))

    @property
    def products(self) -> dict[str, Any]:
        return dict(self._get("products", default={}))

    @property
    def metadata(self) -> dict[str, Any]:
        return dict(self._get("metadata", default={}))

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def ensure_runtime_directories(self) -> None:
        """
        Create runtime-generated directories only when needed.
        """
        for path in [
            self.logs_path,
            self.results_path,
            self.figures_path,
            self.tmp_path,
            self.cache_path,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def as_dict(self) -> dict[str, Any]:
        return dict(self._cfg)

    def summary(self) -> None:
        print("=" * 80)
        print("PrimeNet Configuration")
        print("=" * 80)
        print(f"Project root : {self.project_root}")
        print(f"Config file  : {self.config_file}")
        print(f"Project      : {self.project_name}")
        print(f"Version      : {self.project_version}")
        print()
        print("Resolved paths:")
        print(f"  Repository : {self.repository_path}")
        print(f"  Catalog    : {self.catalog_path}")
        print(f"  Database   : {self.catalog_database}")
        print(f"  Core       : {self.core_path}")
        print(f"  Results    : {self.results_path}")
        print(f"  Figures    : {self.figures_path}")
        print(f"  Logs       : {self.logs_path}")
        print(f"  Temp       : {self.tmp_path}")
        print(f"  Cache      : {self.cache_path}")
        print("=" * 80)


def main() -> int:
    try:
        cfg = Configuration()
        cfg.summary()
        return 0
    except ConfigurationError as exc:
        print("PrimeNet configuration error:")
        print(exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())