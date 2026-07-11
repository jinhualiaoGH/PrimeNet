"""
PrimeNet Platform Configuration Service v1.1.0

Provides one canonical source for Platform paths, repository extent,
campaign scope, and runtime defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


PLATFORM_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PLATFORM_ROOT / "config" / "primenet_config.yaml"


@dataclass(frozen=True)
class PlatformPaths:
    platform_root: Path
    repository_root: Path
    ranges_dir: Path
    gaps_dir: Path
    metadata_dir: Path
    logs_dir: Path
    index_dir: Path
    backups_dir: Path


@dataclass(frozen=True)
class RepositoryExtent:
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 1:
            raise ValueError("Repository extent start must be >= 1.")

        if self.end < self.start:
            raise ValueError(
                "Repository extent end must be >= repository extent start."
            )


@dataclass(frozen=True)
class CampaignScope:
    start: int
    end: int
    range_size: int
    segment_size: int

    def __post_init__(self) -> None:
        if self.start < 1:
            raise ValueError("Campaign start must be >= 1.")

        if self.end < self.start:
            raise ValueError(
                "Campaign end must be >= campaign start."
            )

        if self.range_size <= 0:
            raise ValueError("Campaign range_size must be > 0.")

        if self.segment_size <= 0:
            raise ValueError("Campaign segment_size must be > 0.")


@dataclass(frozen=True)
class PlatformConfiguration:
    config_path: Path
    raw: dict[str, Any]
    paths: PlatformPaths
    repository_extent: RepositoryExtent
    campaign: CampaignScope

    def section(self, name: str) -> dict[str, Any]:
        value = self.raw.get(name, {})

        if not isinstance(value, dict):
            raise ValueError(
                f"Configuration section {name!r} must be a mapping."
            )

        return value


def _resolve_path(value: str | Path, base: Path) -> Path:
    path = Path(value).expanduser()

    if not path.is_absolute():
        path = base / path

    return path.resolve()


def _require_mapping(
    raw: dict[str, Any],
    name: str,
) -> dict[str, Any]:
    value = raw.get(name)

    if not isinstance(value, dict):
        raise ValueError(
            f"Missing or invalid {name!r} configuration section."
        )

    return value


def _require_int(
    section: dict[str, Any],
    key: str,
    qualified_name: str,
) -> int:
    value = section.get(key)

    if value is None:
        raise ValueError(
            f"Missing required configuration: {qualified_name}"
        )

    if isinstance(value, bool):
        raise ValueError(
            f"Configuration value {qualified_name} must be an integer."
        )

    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Configuration value {qualified_name} must be an integer."
        ) from exc


def load_platform_config(
    config_path: str | Path | None = None,
) -> PlatformConfiguration:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    path = path.expanduser().resolve()

    if not path.is_file():
        raise FileNotFoundError(
            f"PrimeNet Platform configuration not found: {path}"
        )

    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    if not isinstance(raw, dict):
        raise ValueError(
            f"Configuration root must be a mapping: {path}"
        )

    repository = _require_mapping(raw, "repository")
    campaign_section = _require_mapping(raw, "campaign")

    repository_root_value = repository.get("root")

    if not repository_root_value:
        raise ValueError(
            "Missing required configuration: repository.root"
        )

    repository_root = _resolve_path(
        repository_root_value,
        path.parent,
    )

    def repository_path(
        key: str,
        default_relative: str,
    ) -> Path:
        value = repository.get(key)

        if value:
            return _resolve_path(value, path.parent)

        return (repository_root / default_relative).resolve()

    paths = PlatformPaths(
        platform_root=PLATFORM_ROOT,
        repository_root=repository_root,
        ranges_dir=repository_path("ranges_dir", "ranges"),
        gaps_dir=repository_path("gaps_dir", "gaps"),
        metadata_dir=repository_path("metadata_dir", "metadata"),
        logs_dir=repository_path("logs_dir", "logs"),
        index_dir=repository_path("index_dir", "index"),
        backups_dir=repository_path("backups_dir", "backups"),
    )

    repository_extent = RepositoryExtent(
        start=_require_int(
            repository,
            "extent_start",
            "repository.extent_start",
        ),
        end=_require_int(
            repository,
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

    if campaign.start < repository_extent.start:
        raise ValueError(
            "Campaign start lies below the repository extent."
        )

    if campaign.end > repository_extent.end:
        raise ValueError(
            "Campaign end lies above the repository extent."
        )

    return PlatformConfiguration(
        config_path=path,
        raw=raw,
        paths=paths,
        repository_extent=repository_extent,
        campaign=campaign,
    )