"""
PrimeNet Repository Service

Scientific-facing repository facade over the canonical PrimeNet Platform
repository infrastructure.

Design rules:
    - Platform.core.repository owns physical repository discovery,
      parsing, numeric ordering, and topology validation.
    - Platform.core.query_repository owns global prime-index and
      gap-index coordinate queries.
    - Observatories consume this facade and do not independently
      implement repository topology rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

from core.config import Configuration
from core.logger import PrimeNetLogger
from core.paths import Paths

from Platform.core.query_repository import PrimeQueryRepository
from Platform.core.range_files import RangeFile, validate_adjacency
from Platform.core.repository import PrimeRepository


@dataclass(frozen=True)
class PrimeRangeFile:
    """
    Compatibility record used by existing PrimeNet observatories.

    The canonical Platform layer owns physical range-file discovery and
    validation. This record preserves the existing Observatory-facing
    interface while downstream consumers are migrated incrementally.
    """

    file_path: Path
    start: int
    end: int
    size_bytes: int

    @property
    def name(self) -> str:
        return self.file_path.name


class Repository:
    """
    Scientific-facing PrimeNet repository facade.

    Physical prime repository responsibilities are delegated to the
    canonical Platform repository service. Global index-coordinate
    queries are delegated lazily to PrimeQueryRepository.
    """

    def __init__(
        self,
        config: Configuration,
        paths: Paths,
        logger: PrimeNetLogger | None = None,
    ) -> None:
        self.config = config
        self.paths = paths
        self.logger = logger

        self._prime_repository: PrimeRepository | None = None
        self._query_repository: PrimeQueryRepository | None = None

    @property
    def prime_repository(self) -> PrimeRepository:
        """
        Return the canonical physical prime repository.
        """
        if self._prime_repository is None:
            self._prime_repository = PrimeRepository()

        return self._prime_repository

    @property
    def query_repository(self) -> PrimeQueryRepository:
        """
        Return the canonical scientific/index-coordinate query service.
        """
        if self._query_repository is None:
            self._query_repository = PrimeQueryRepository()

        return self._query_repository

    def prime_sources(self) -> list[Path]:
        """
        Return the canonical physical prime repository directory.

        This method is retained for Observatory compatibility.
        """
        return [
            self.prime_repository.ranges_dir,
        ]

    def list_prime_files(self) -> list[PrimeRangeFile]:
        """
        Return canonical prime partitions through the compatibility
        record expected by existing observatories.
        """
        records: list[PrimeRangeFile] = []

        for range_file in self.prime_repository.range_files():
            try:
                size_bytes = range_file.path.stat().st_size
            except OSError:
                size_bytes = 0

            records.append(
                PrimeRangeFile(
                    file_path=range_file.path,
                    start=range_file.start,
                    end=range_file.end,
                    size_bytes=size_bytes,
                )
            )

        return records

    def validate_prime_ranges(
        self,
        files: list[PrimeRangeFile],
    ) -> list[str]:
        """
        Validate Observatory-facing prime records using the canonical
        Platform adjacency contract.
        """
        if not files:
            return [
                "No prime files found.",
            ]

        range_files = [
            RangeFile(
                path=record.file_path,
                kind="primes",
                start=record.start,
                end=record.end,
            )
            for record in files
        ]

        issues = validate_adjacency(range_files)

        return [
            (
                f"Range {issue['issue_type'].lower()}: "
                f"{issue['previous']} ends at "
                f"{issue['previous_end']}, "
                f"{issue['current']} starts at "
                f"{issue['current_start']}"
            )
            for issue in issues
        ]

    def summary(self) -> None:
        files = self.list_prime_files()

        total_size = sum(
            file.size_bytes
            for file in files
        )

        print("=" * 80)
        print("PrimeNet Repository Service")
        print("=" * 80)

        print(
            f"Prime directory   : "
            f"{self.prime_repository.ranges_dir}"
        )
        print(
            f"Prime files found : {len(files)}"
        )
        print(
            f"Total size        : "
            f"{total_size / (1024 ** 3):.6f} GB"
        )

        if files:
            print(
                f"First range       : "
                f"{files[0].start} -> {files[0].end}"
            )
            print(
                f"Last range        : "
                f"{files[-1].start} -> {files[-1].end}"
            )

        warnings = self.validate_prime_ranges(files)

        if warnings:
            print("Validation warnings:")
            for warning in warnings:
                print(f"  WARNING: {warning}")
        else:
            print("Range validation  : PASSED")

        print("=" * 80)

    def close(self) -> None:
        """
        Release the lazily constructed query service when present.
        """
        if self._query_repository is not None:
            self._query_repository.close()
            self._query_repository = None

    def __enter__(self) -> "Repository":
        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        self.close()


def main() -> int:
    cfg = Configuration()
    paths = Paths(cfg)
    logger = PrimeNetLogger(cfg, paths)

    with Repository(
        cfg,
        paths,
        logger,
    ) as repository:
        repository.summary()

    return 0


if __name__ == "__main__":
    sys.exit(main())
