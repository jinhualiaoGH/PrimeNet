"""
PrimeNet Platform Configuration Service v2.0.0
===============================================

Canonical, read-only configuration service for PrimeNet Platform.

This module loads and validates:

    Platform/config/primenet_config.yaml

It provides typed access to:

    - platform identity and root;
    - canonical repository paths;
    - canonical product paths;
    - repository physical extent;
    - campaign scope;
    - repository-generation defaults;
    - runtime defaults;
    - validation policy.

Architectural role
------------------
This module is the canonical configuration authority for PrimeNet core
modules.

It does not:

    - create directories;
    - modify configuration files;
    - write logs or metadata;
    - build or verify repository data;
    - load repository execution plans such as repository_build.yaml.

The production execution plan remains separate:

    Platform/config/repository_build.yaml

Design principles
-----------------
1. Importing this module performs no file-system configuration reads.
2. Configuration is loaded only when load_platform_config() is called.
3. All canonical integer values are parsed strictly.
4. Repository and product paths are resolved deterministically.
5. Canonical paths must not collide.
6. Repository child paths must remain beneath repository.root.
7. Product child paths must remain beneath products.root.
8. Repository and campaign ranges must align to the canonical partition grid.
9. Campaign runtime sizes must agree with official generation defaults.
10. Configuration loading is strictly read-only.

Direct execution
----------------
    py -m Platform.core.platform_config
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


SERVICE_NAME = "PrimeNet Platform Configuration Service"
SERVICE_VERSION = "2.0.0"

SOURCE_PLATFORM_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = (
    SOURCE_PLATFORM_ROOT
    / "config"
    / "primenet_config.yaml"
)


@dataclass(frozen=True)
class PlatformIdentity:
    """
    PrimeNet Platform identity.
    """

    name: str
    version: str
    configured_root: Path
    source_root: Path


@dataclass(frozen=True)
class PlatformPaths:
    """
    Canonical PrimeNet repository and platform paths.

    Existing field names are preserved for backward compatibility.
    """

    platform_root: Path

    repository_root: Path
    ranges_dir: Path
    gaps_dir: Path
    metadata_dir: Path
    logs_dir: Path
    index_dir: Path
    manifests_dir: Path
    backups_dir: Path
    scripts_dir: Path


@dataclass(frozen=True)
class ProductPaths:
    """
    Canonical PrimeNet product-publication paths.
    """

    root: Path
    results_dir: Path
    figures_dir: Path
    atlases_dir: Path
    reports_dir: Path
    archives_dir: Path
    publications_dir: Path


@dataclass(frozen=True)
class RepositoryExtent:
    """
    Inclusive physical repository numeric extent.
    """

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 1:
            raise ValueError(
                "Repository extent start must be >= 1."
            )

        if self.end < self.start:
            raise ValueError(
                "Repository extent end must be >= "
                "repository extent start."
            )

    @property
    def length(self) -> int:
        return self.end - self.start + 1


@dataclass(frozen=True)
class CampaignScope:
    """
    Default campaign execution scope.
    """

    start: int
    end: int
    range_size: int
    segment_size: int

    def __post_init__(self) -> None:
        if self.start < 1:
            raise ValueError(
                "Campaign start must be >= 1."
            )

        if self.end < self.start:
            raise ValueError(
                "Campaign end must be >= campaign start."
            )

        if self.range_size <= 0:
            raise ValueError(
                "Campaign range_size must be > 0."
            )

        if self.segment_size <= 0:
            raise ValueError(
                "Campaign segment_size must be > 0."
            )

    @property
    def length(self) -> int:
        return self.end - self.start + 1

    @property
    def partition_count(self) -> int:
        return self.length // self.range_size


@dataclass(frozen=True)
class RepositoryGeneration:
    """
    Canonical repository-generation defaults.
    """

    official_range_size: int
    official_segment_size: int
    official_file_policy: str

    experimental_range_size: int
    experimental_segment_size: int

    overwrite_existing: bool

    def __post_init__(self) -> None:
        if self.official_range_size <= 0:
            raise ValueError(
                "repository_generation.official_range_size "
                "must be > 0."
            )

        if self.official_segment_size <= 0:
            raise ValueError(
                "repository_generation.official_segment_size "
                "must be > 0."
            )

        if self.experimental_range_size <= 0:
            raise ValueError(
                "repository_generation.experimental_range_size "
                "must be > 0."
            )

        if self.experimental_segment_size <= 0:
            raise ValueError(
                "repository_generation.experimental_segment_size "
                "must be > 0."
            )

        if not self.official_file_policy:
            raise ValueError(
                "repository_generation.official_file_policy "
                "must not be empty."
            )


@dataclass(frozen=True)
class RuntimeSettings:
    """
    Canonical runtime defaults.
    """

    log_level: str
    write_mode: str
    timestamp_format: str

    def __post_init__(self) -> None:
        if not self.log_level:
            raise ValueError(
                "runtime.log_level must not be empty."
            )

        if not self.write_mode:
            raise ValueError(
                "runtime.write_mode must not be empty."
            )

        if not self.timestamp_format:
            raise ValueError(
                "runtime.timestamp_format must not be empty."
            )


@dataclass(frozen=True)
class ValidationSettings:
    """
    Canonical repository validation policy.
    """

    validate_range_boundaries: bool
    validate_sorted_primes: bool
    validate_min_max_prime: bool
    validate_file_exists: bool
    validate_inventory: bool


@dataclass(frozen=True)
class PlatformConfiguration:
    """
    Fully resolved and validated PrimeNet configuration.
    """

    config_path: Path
    raw: dict[str, Any]

    platform: PlatformIdentity
    paths: PlatformPaths
    products: ProductPaths

    repository_extent: RepositoryExtent
    campaign: CampaignScope
    repository_generation: RepositoryGeneration
    runtime: RuntimeSettings
    validation: ValidationSettings

    def section(
        self,
        name: str,
    ) -> dict[str, Any]:
        """
        Return one raw top-level mapping section.

        A shallow copy is returned so callers cannot mutate the stored
        configuration dictionary through this method.
        """
        value = self.raw.get(
            name,
            {},
        )

        if not isinstance(
            value,
            dict,
        ):
            raise ValueError(
                f"Configuration section "
                f"{name!r} must be a mapping."
            )

        return dict(value)

    def as_dict(self) -> dict[str, Any]:
        """
        Return a serializable resolved configuration summary.
        """
        return {
            "service_version": SERVICE_VERSION,
            "config_path": str(
                self.config_path
            ),
            "platform": {
                "name": self.platform.name,
                "version": self.platform.version,
                "configured_root": str(
                    self.platform.configured_root
                ),
                "source_root": str(
                    self.platform.source_root
                ),
            },
            "repository": {
                "root": str(
                    self.paths.repository_root
                ),
                "ranges_dir": str(
                    self.paths.ranges_dir
                ),
                "gaps_dir": str(
                    self.paths.gaps_dir
                ),
                "metadata_dir": str(
                    self.paths.metadata_dir
                ),
                "logs_dir": str(
                    self.paths.logs_dir
                ),
                "index_dir": str(
                    self.paths.index_dir
                ),
                "manifests_dir": str(
                    self.paths.manifests_dir
                ),
                "backups_dir": str(
                    self.paths.backups_dir
                ),
                "scripts_dir": str(
                    self.paths.scripts_dir
                ),
                "extent_start": (
                    self.repository_extent.start
                ),
                "extent_end": (
                    self.repository_extent.end
                ),
                "extent_length": (
                    self.repository_extent.length
                ),
            },
            "products": {
                "root": str(
                    self.products.root
                ),
                "results_dir": str(
                    self.products.results_dir
                ),
                "figures_dir": str(
                    self.products.figures_dir
                ),
                "atlases_dir": str(
                    self.products.atlases_dir
                ),
                "reports_dir": str(
                    self.products.reports_dir
                ),
                "archives_dir": str(
                    self.products.archives_dir
                ),
                "publications_dir": str(
                    self.products.publications_dir
                ),
            },
            "campaign": {
                "start": self.campaign.start,
                "end": self.campaign.end,
                "length": self.campaign.length,
                "range_size": (
                    self.campaign.range_size
                ),
                "segment_size": (
                    self.campaign.segment_size
                ),
                "partition_count": (
                    self.campaign.partition_count
                ),
            },
            "repository_generation": {
                "official_range_size": (
                    self.repository_generation
                    .official_range_size
                ),
                "official_segment_size": (
                    self.repository_generation
                    .official_segment_size
                ),
                "official_file_policy": (
                    self.repository_generation
                    .official_file_policy
                ),
                "experimental_range_size": (
                    self.repository_generation
                    .experimental_range_size
                ),
                "experimental_segment_size": (
                    self.repository_generation
                    .experimental_segment_size
                ),
                "overwrite_existing": (
                    self.repository_generation
                    .overwrite_existing
                ),
            },
            "runtime": {
                "log_level": (
                    self.runtime.log_level
                ),
                "write_mode": (
                    self.runtime.write_mode
                ),
                "timestamp_format": (
                    self.runtime.timestamp_format
                ),
            },
            "validation": {
                "validate_range_boundaries": (
                    self.validation
                    .validate_range_boundaries
                ),
                "validate_sorted_primes": (
                    self.validation
                    .validate_sorted_primes
                ),
                "validate_min_max_prime": (
                    self.validation
                    .validate_min_max_prime
                ),
                "validate_file_exists": (
                    self.validation
                    .validate_file_exists
                ),
                "validate_inventory": (
                    self.validation
                    .validate_inventory
                ),
            },
        }


def _require_mapping(
    raw: Mapping[str, Any],
    name: str,
) -> dict[str, Any]:
    value = raw.get(name)

    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            f"Missing or invalid {name!r} "
            "configuration section."
        )

    return dict(value)


def _optional_mapping(
    raw: Mapping[str, Any],
    name: str,
) -> dict[str, Any]:
    value = raw.get(
        name,
        {},
    )

    if value is None:
        return {}

    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            f"Configuration section "
            f"{name!r} must be a mapping."
        )

    return dict(value)


def _require_string(
    section: Mapping[str, Any],
    key: str,
    qualified_name: str,
) -> str:
    value = section.get(key)

    if value is None:
        raise ValueError(
            f"Missing required configuration: "
            f"{qualified_name}"
        )

    if not isinstance(
        value,
        str,
    ):
        raise ValueError(
            f"Configuration value "
            f"{qualified_name} must be a string."
        )

    result = value.strip()

    if not result:
        raise ValueError(
            f"Configuration value "
            f"{qualified_name} must not be empty."
        )

    return result


def _optional_string(
    section: Mapping[str, Any],
    key: str,
    default: str,
    qualified_name: str,
) -> str:
    value = section.get(
        key,
        default,
    )

    if not isinstance(
        value,
        str,
    ):
        raise ValueError(
            f"Configuration value "
            f"{qualified_name} must be a string."
        )

    result = value.strip()

    if not result:
        raise ValueError(
            f"Configuration value "
            f"{qualified_name} must not be empty."
        )

    return result


def _strict_int_value(
    value: Any,
    qualified_name: str,
) -> int:
    """
    Parse an integer without silently truncating floating-point values.
    """
    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            f"Configuration value "
            f"{qualified_name} must be an integer."
        )

    if isinstance(
        value,
        int,
    ):
        return value

    if isinstance(
        value,
        str,
    ):
        stripped = value.strip()

        if not stripped:
            raise ValueError(
                f"Configuration value "
                f"{qualified_name} must be an integer."
            )

        signless = (
            stripped[1:]
            if stripped[0] in "+-"
            else stripped
        )

        if not signless.isdigit():
            raise ValueError(
                f"Configuration value "
                f"{qualified_name} must be an integer."
            )

        return int(stripped)

    raise ValueError(
        f"Configuration value "
        f"{qualified_name} must be an integer."
    )


def _require_int(
    section: Mapping[str, Any],
    key: str,
    qualified_name: str,
) -> int:
    if key not in section:
        raise ValueError(
            f"Missing required configuration: "
            f"{qualified_name}"
        )

    return _strict_int_value(
        section[key],
        qualified_name,
    )


def _optional_int(
    section: Mapping[str, Any],
    key: str,
    default: int,
    qualified_name: str,
) -> int:
    value = section.get(
        key,
        default,
    )

    return _strict_int_value(
        value,
        qualified_name,
    )


def _strict_bool_value(
    value: Any,
    qualified_name: str,
) -> bool:
    if isinstance(
        value,
        bool,
    ):
        return value

    raise ValueError(
        f"Configuration value "
        f"{qualified_name} must be a boolean."
    )


def _optional_bool(
    section: Mapping[str, Any],
    key: str,
    default: bool,
    qualified_name: str,
) -> bool:
    value = section.get(
        key,
        default,
    )

    return _strict_bool_value(
        value,
        qualified_name,
    )


def _resolve_path(
    value: str | Path,
    base: Path,
) -> Path:
    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            "Path configuration values "
            "must be strings or Path objects."
        )

    path = Path(value).expanduser()

    if not path.is_absolute():
        path = base / path

    return path.resolve()


def _require_path(
    section: Mapping[str, Any],
    key: str,
    qualified_name: str,
    base: Path,
) -> Path:
    value = section.get(key)

    if value in (
        None,
        "",
    ):
        raise ValueError(
            f"Missing required configuration: "
            f"{qualified_name}"
        )

    if not isinstance(
        value,
        (str, Path),
    ):
        raise ValueError(
            f"Configuration value "
            f"{qualified_name} must be a path string."
        )

    return _resolve_path(
        value,
        base,
    )


def _optional_path(
    section: Mapping[str, Any],
    key: str,
    default: Path,
    qualified_name: str,
    base: Path,
) -> Path:
    value = section.get(key)

    if value in (
        None,
        "",
    ):
        return default.resolve()

    if not isinstance(
        value,
        (str, Path),
    ):
        raise ValueError(
            f"Configuration value "
            f"{qualified_name} must be a path string."
        )

    return _resolve_path(
        value,
        base,
    )


def _is_relative_to(
    path: Path,
    parent: Path,
) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False

    return True


def _validate_child_paths(
    *,
    root: Path,
    children: Mapping[str, Path],
    root_name: str,
) -> None:
    for name, path in children.items():
        if path == root:
            raise ValueError(
                f"Configuration path {name} "
                f"must not equal {root_name}."
            )

        if not _is_relative_to(
            path,
            root,
        ):
            raise ValueError(
                f"Configuration path {name} "
                f"must remain beneath {root_name}: "
                f"{path}"
            )


def _validate_path_collisions(
    paths: Mapping[str, Path],
) -> None:
    names_by_path: dict[
        Path,
        list[str],
    ] = {}

    for name, path in paths.items():
        names_by_path.setdefault(
            path,
            [],
        ).append(name)

    collisions = {
        path: names
        for path, names
        in names_by_path.items()
        if len(names) > 1
    }

    if collisions:
        details = "; ".join(
            f"{path}: {', '.join(names)}"
            for path, names
            in collisions.items()
        )

        raise ValueError(
            "Canonical configuration paths "
            f"must not collide: {details}"
        )


def _validate_partition_grid(
    *,
    extent: RepositoryExtent,
    campaign: CampaignScope,
    generation: RepositoryGeneration,
) -> None:
    official_range_size = (
        generation.official_range_size
    )

    if (
        campaign.range_size
        != official_range_size
    ):
        raise ValueError(
            "campaign.range_size must equal "
            "repository_generation."
            "official_range_size."
        )

    if (
        campaign.segment_size
        != generation.official_segment_size
    ):
        raise ValueError(
            "campaign.segment_size must equal "
            "repository_generation."
            "official_segment_size."
        )

    if (
        official_range_size
        % generation.official_segment_size
        != 0
    ):
        raise ValueError(
            "repository_generation."
            "official_range_size must be "
            "divisible by official_segment_size."
        )

    if (
        generation.experimental_range_size
        % generation.experimental_segment_size
        != 0
    ):
        raise ValueError(
            "repository_generation."
            "experimental_range_size must be "
            "divisible by "
            "experimental_segment_size."
        )

    if (
        extent.length
        % official_range_size
        != 0
    ):
        raise ValueError(
            "Repository extent length must be "
            "divisible by the official range size."
        )

    campaign_start_offset = (
        campaign.start
        - extent.start
    )

    if (
        campaign_start_offset
        % official_range_size
        != 0
    ):
        raise ValueError(
            "Campaign start must align with "
            "the canonical repository partition grid."
        )

    if (
        campaign.length
        % official_range_size
        != 0
    ):
        raise ValueError(
            "Campaign length must be divisible "
            "by the canonical range size."
        )


def _load_yaml(
    path: Path,
) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(
            "PrimeNet Platform configuration "
            f"not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        raw = yaml.safe_load(handle) or {}

    if not isinstance(
        raw,
        dict,
    ):
        raise ValueError(
            "Configuration root must be "
            f"a mapping: {path}"
        )

    return dict(raw)


def load_platform_config(
    config_path: str | Path | None = None,
) -> PlatformConfiguration:
    """
    Load and validate the canonical PrimeNet platform configuration.

    This operation is read-only.
    """
    if config_path is None:
        path = DEFAULT_CONFIG_PATH
    else:
        path = Path(config_path)

    path = (
        path
        .expanduser()
        .resolve()
    )

    raw = _load_yaml(path)

    platform_section = _require_mapping(
        raw,
        "platform",
    )
    repository_section = _require_mapping(
        raw,
        "repository",
    )
    products_section = _require_mapping(
        raw,
        "products",
    )
    campaign_section = _require_mapping(
        raw,
        "campaign",
    )
    generation_section = _require_mapping(
        raw,
        "repository_generation",
    )
    runtime_section = _optional_mapping(
        raw,
        "runtime",
    )
    validation_section = _optional_mapping(
        raw,
        "validation",
    )

    config_base = path.parent

    configured_platform_root = (
        _require_path(
            platform_section,
            "root",
            "platform.root",
            config_base,
        )
    )

    platform = PlatformIdentity(
        name=_require_string(
            platform_section,
            "name",
            "platform.name",
        ),
        version=_require_string(
            platform_section,
            "version",
            "platform.version",
        ),
        configured_root=(
            configured_platform_root
        ),
        source_root=(
            SOURCE_PLATFORM_ROOT
        ),
    )

    if (
        configured_platform_root
        != SOURCE_PLATFORM_ROOT
    ):
        raise ValueError(
            "Configured platform.root does "
            "not match the executing Platform "
            "source root.\n"
            f"Configured: {configured_platform_root}\n"
            f"Source:     {SOURCE_PLATFORM_ROOT}"
        )

    repository_root = _require_path(
        repository_section,
        "root",
        "repository.root",
        config_base,
    )

    repository_children = {
        "repository.ranges_dir": (
            _optional_path(
                repository_section,
                "ranges_dir",
                repository_root / "ranges",
                "repository.ranges_dir",
                config_base,
            )
        ),
        "repository.gaps_dir": (
            _optional_path(
                repository_section,
                "gaps_dir",
                repository_root / "gaps",
                "repository.gaps_dir",
                config_base,
            )
        ),
        "repository.metadata_dir": (
            _optional_path(
                repository_section,
                "metadata_dir",
                repository_root / "metadata",
                "repository.metadata_dir",
                config_base,
            )
        ),
        "repository.logs_dir": (
            _optional_path(
                repository_section,
                "logs_dir",
                repository_root / "logs",
                "repository.logs_dir",
                config_base,
            )
        ),
        "repository.index_dir": (
            _optional_path(
                repository_section,
                "index_dir",
                repository_root / "index",
                "repository.index_dir",
                config_base,
            )
        ),
        "repository.manifests_dir": (
            _optional_path(
                repository_section,
                "manifests_dir",
                repository_root / "manifests",
                "repository.manifests_dir",
                config_base,
            )
        ),
        "repository.backups_dir": (
            _optional_path(
                repository_section,
                "backups_dir",
                repository_root / "backups",
                "repository.backups_dir",
                config_base,
            )
        ),
        "repository.scripts_dir": (
            _optional_path(
                repository_section,
                "scripts_dir",
                repository_root / "scripts",
                "repository.scripts_dir",
                config_base,
            )
        ),
    }

    _validate_child_paths(
        root=repository_root,
        children=repository_children,
        root_name="repository.root",
    )

    paths = PlatformPaths(
        platform_root=(
            SOURCE_PLATFORM_ROOT
        ),
        repository_root=(
            repository_root
        ),
        ranges_dir=(
            repository_children[
                "repository.ranges_dir"
            ]
        ),
        gaps_dir=(
            repository_children[
                "repository.gaps_dir"
            ]
        ),
        metadata_dir=(
            repository_children[
                "repository.metadata_dir"
            ]
        ),
        logs_dir=(
            repository_children[
                "repository.logs_dir"
            ]
        ),
        index_dir=(
            repository_children[
                "repository.index_dir"
            ]
        ),
        manifests_dir=(
            repository_children[
                "repository.manifests_dir"
            ]
        ),
        backups_dir=(
            repository_children[
                "repository.backups_dir"
            ]
        ),
        scripts_dir=(
            repository_children[
                "repository.scripts_dir"
            ]
        ),
    )

    products_root = _require_path(
        products_section,
        "root",
        "products.root",
        config_base,
    )

    product_children = {
        "products.results_dir": (
            _optional_path(
                products_section,
                "results_dir",
                products_root / "results",
                "products.results_dir",
                config_base,
            )
        ),
        "products.figures_dir": (
            _optional_path(
                products_section,
                "figures_dir",
                products_root / "figures",
                "products.figures_dir",
                config_base,
            )
        ),
        "products.atlases_dir": (
            _optional_path(
                products_section,
                "atlases_dir",
                products_root / "atlases",
                "products.atlases_dir",
                config_base,
            )
        ),
        "products.reports_dir": (
            _optional_path(
                products_section,
                "reports_dir",
                products_root / "reports",
                "products.reports_dir",
                config_base,
            )
        ),
        "products.archives_dir": (
            _optional_path(
                products_section,
                "archives_dir",
                products_root / "archives",
                "products.archives_dir",
                config_base,
            )
        ),
        "products.publications_dir": (
            _optional_path(
                products_section,
                "publications_dir",
                products_root / "publications",
                "products.publications_dir",
                config_base,
            )
        ),
    }

    _validate_child_paths(
        root=products_root,
        children=product_children,
        root_name="products.root",
    )

    products = ProductPaths(
        root=products_root,
        results_dir=(
            product_children[
                "products.results_dir"
            ]
        ),
        figures_dir=(
            product_children[
                "products.figures_dir"
            ]
        ),
        atlases_dir=(
            product_children[
                "products.atlases_dir"
            ]
        ),
        reports_dir=(
            product_children[
                "products.reports_dir"
            ]
        ),
        archives_dir=(
            product_children[
                "products.archives_dir"
            ]
        ),
        publications_dir=(
            product_children[
                "products.publications_dir"
            ]
        ),
    )

    repository_extent = RepositoryExtent(
        start=_require_int(
            repository_section,
            "extent_start",
            "repository.extent_start",
        ),
        end=_require_int(
            repository_section,
            "extent_end",
            "repository.extent_end",
        ),
    )

    campaign = CampaignScope(
        start=_require_int(
            campaign_section,
            "start",
            "campaign.start",
        ),
        end=_require_int(
            campaign_section,
            "end",
            "campaign.end",
        ),
        range_size=_require_int(
            campaign_section,
            "range_size",
            "campaign.range_size",
        ),
        segment_size=_require_int(
            campaign_section,
            "segment_size",
            "campaign.segment_size",
        ),
    )

    generation = RepositoryGeneration(
        official_range_size=(
            _require_int(
                generation_section,
                "official_range_size",
                (
                    "repository_generation."
                    "official_range_size"
                ),
            )
        ),
        official_segment_size=(
            _require_int(
                generation_section,
                "official_segment_size",
                (
                    "repository_generation."
                    "official_segment_size"
                ),
            )
        ),
        official_file_policy=(
            _require_string(
                generation_section,
                "official_file_policy",
                (
                    "repository_generation."
                    "official_file_policy"
                ),
            )
        ),
        experimental_range_size=(
            _require_int(
                generation_section,
                "experimental_range_size",
                (
                    "repository_generation."
                    "experimental_range_size"
                ),
            )
        ),
        experimental_segment_size=(
            _require_int(
                generation_section,
                "experimental_segment_size",
                (
                    "repository_generation."
                    "experimental_segment_size"
                ),
            )
        ),
        overwrite_existing=(
            _optional_bool(
                generation_section,
                "overwrite_existing",
                False,
                (
                    "repository_generation."
                    "overwrite_existing"
                ),
            )
        ),
    )

    runtime = RuntimeSettings(
        log_level=_optional_string(
            runtime_section,
            "log_level",
            "INFO",
            "runtime.log_level",
        ),
        write_mode=_optional_string(
            runtime_section,
            "write_mode",
            "direct",
            "runtime.write_mode",
        ),
        timestamp_format=(
            _optional_string(
                runtime_section,
                "timestamp_format",
                "iso8601",
                "runtime.timestamp_format",
            )
        ),
    )

    validation = ValidationSettings(
        validate_range_boundaries=(
            _optional_bool(
                validation_section,
                "validate_range_boundaries",
                True,
                (
                    "validation."
                    "validate_range_boundaries"
                ),
            )
        ),
        validate_sorted_primes=(
            _optional_bool(
                validation_section,
                "validate_sorted_primes",
                True,
                (
                    "validation."
                    "validate_sorted_primes"
                ),
            )
        ),
        validate_min_max_prime=(
            _optional_bool(
                validation_section,
                "validate_min_max_prime",
                True,
                (
                    "validation."
                    "validate_min_max_prime"
                ),
            )
        ),
        validate_file_exists=(
            _optional_bool(
                validation_section,
                "validate_file_exists",
                True,
                (
                    "validation."
                    "validate_file_exists"
                ),
            )
        ),
        validate_inventory=(
            _optional_bool(
                validation_section,
                "validate_inventory",
                True,
                (
                    "validation."
                    "validate_inventory"
                ),
            )
        ),
    )

    if (
        campaign.start
        < repository_extent.start
    ):
        raise ValueError(
            "Campaign start lies below "
            "the repository extent."
        )

    if (
        campaign.end
        > repository_extent.end
    ):
        raise ValueError(
            "Campaign end lies above "
            "the repository extent."
        )

    _validate_partition_grid(
        extent=repository_extent,
        campaign=campaign,
        generation=generation,
    )

    _validate_path_collisions(
        {
            "repository.ranges_dir": (
                paths.ranges_dir
            ),
            "repository.gaps_dir": (
                paths.gaps_dir
            ),
            "repository.metadata_dir": (
                paths.metadata_dir
            ),
            "repository.logs_dir": (
                paths.logs_dir
            ),
            "repository.index_dir": (
                paths.index_dir
            ),
            "repository.manifests_dir": (
                paths.manifests_dir
            ),
            "repository.backups_dir": (
                paths.backups_dir
            ),
            "repository.scripts_dir": (
                paths.scripts_dir
            ),
            "products.results_dir": (
                products.results_dir
            ),
            "products.figures_dir": (
                products.figures_dir
            ),
            "products.atlases_dir": (
                products.atlases_dir
            ),
            "products.reports_dir": (
                products.reports_dir
            ),
            "products.archives_dir": (
                products.archives_dir
            ),
            "products.publications_dir": (
                products.publications_dir
            ),
        }
    )

    return PlatformConfiguration(
        config_path=path,
        raw=raw,
        platform=platform,
        paths=paths,
        products=products,
        repository_extent=(
            repository_extent
        ),
        campaign=campaign,
        repository_generation=(
            generation
        ),
        runtime=runtime,
        validation=validation,
    )


def main() -> int:
    """
    Print the resolved canonical configuration.

    This operation is read-only.
    """
    try:
        config = load_platform_config()

        print("=" * 80)
        print(
            f"{SERVICE_NAME} "
            f"v{SERVICE_VERSION}"
        )
        print("=" * 80)
        print(
            json.dumps(
                config.as_dict(),
                indent=2,
            )
        )
        print("=" * 80)
        print(
            "Configuration loaded and "
            "validated successfully."
        )
        print(
            "No files or directories were modified."
        )
        print("=" * 80)

        return 0

    except (
        FileNotFoundError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            f"[FAILED] {exc}",
            file=sys.stderr,
        )
        return 2

    except Exception as exc:
        print(
            f"[FAILED] {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())