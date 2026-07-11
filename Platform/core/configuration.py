"""
PrimeNet Configuration Loader
=============================

Central configuration manager for the PrimeNet Platform.
"""

from __future__ import annotations

from pathlib import Path
import yaml


PLATFORM_ROOT = Path(__file__).resolve().parents[1]

CONFIG_DIR = PLATFORM_ROOT / "config"

PRIMENET_CONFIG = CONFIG_DIR / "primenet_config.yaml"
REPOSITORY_CONFIG = CONFIG_DIR / "repository.yaml"


class Configuration:

    def __init__(self):

        self.primenet = self._load(PRIMENET_CONFIG)
        self.repository = self._load(REPOSITORY_CONFIG)

    @staticmethod
    def _load(path: Path):

        if not path.exists():
            raise FileNotFoundError(path)

        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @staticmethod
    def _get_nested(data: dict, keys: list[str], default):
        current = data
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
        return current

    @property
    def repository_root(self):

        return Path(self.repository["repository"]["root"])

    @property
    def segment_size(self):

        return int(self.repository["generation"]["segment_size"])

    @property
    def batch_size(self):

        return int(self.repository["generation"]["batch_size"])

    @property
    def repository_start(self):

        return int(self.repository["repository_limits"]["start"])

    @property
    def repository_end(self):

        return int(self.repository["repository_limits"]["end"])

    @property
    def skip_existing(self):

        return bool(self.repository["driver"]["skip_existing"])

    @property
    def overwrite_existing(self):

        return bool(
            self._get_nested(
                self.repository,
                ["driver", "overwrite_existing"],
                False,
            )
        )

    @property
    def verify_after_generation(self):

        return bool(self.repository["driver"]["verify_after_generation"])

    @property
    def log_runtime(self):

        return bool(self.repository["driver"]["log_runtime"])

    @property
    def progress_step_percent(self):

        return int(
            self._get_nested(
                self.repository,
                ["logging", "progress_step_percent"],
                10,
            )
        )

    @property
    def anomaly_threshold_minutes(self):

        return float(
            self._get_nested(
                self.repository,
                ["quality_metrics", "anomaly_threshold_minutes"],
                60.0,
            )
        )

    @property
    def save_anomaly_log(self):

        return bool(
            self._get_nested(
                self.repository,
                ["quality_metrics", "save_anomaly_log"],
                True,
            )
        )

    @property
    def save_quality_metrics(self):

        return bool(
            self._get_nested(
                self.repository,
                ["quality_metrics", "save_quality_metrics"],
                True,
            )
        )


config = Configuration()
