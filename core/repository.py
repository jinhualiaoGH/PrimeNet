"""
PrimeNet Repository Service

Provides a logical repository view over one or more physical prime-data locations.

Design rule:
    Observatories should not care where prime files physically live.
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
import re
import sys

from core.config import Configuration
from core.paths import Paths
from core.logger import PrimeNetLogger


@dataclass(frozen=True)
class PrimeRangeFile:
    file_path: Path
    start: int
    end: int
    size_bytes: int

    @property
    def name(self) -> str:
        return self.file_path.name


class Repository:
    """
    Logical PrimeNet repository service.
    """

    def __init__(
        self,
        config: Configuration,
        paths: Paths,
        logger: PrimeNetLogger | None = None,
    ):
        self.config = config
        self.paths = paths
        self.logger = logger

    def _log(self, message: str) -> None:
        if self.logger is not None:
            self.logger.info(message)
        else:
            print(message)

    def _parse_prime_range(self, path: Path) -> tuple[int, int] | None:
        nums = re.findall(r"\d+", path.stem)

        if len(nums) >= 2:
            return int(nums[0]), int(nums[1])

        return None

    def prime_sources(self) -> list[Path]:
        repo_cfg = self.config.repository

        sources = repo_cfg.get("prime_sources", [])

        if not sources:
            sources = [
                self.paths.repository / "raw" / "primes",
                self.paths.repository / "ranges",
                self.paths.repository,
            ]

        resolved = []

        for src in sources:
            p = Path(src)

            if not p.is_absolute():
                p = self.paths.project_root / p

            resolved.append(p)

        return resolved

    def list_prime_files(self) -> list[PrimeRangeFile]:
        records: list[PrimeRangeFile] = []

        for source in self.prime_sources():
            if not source.exists():
                self._log(f"[WARN] Prime source not found: {source}")
                continue

            for path in source.rglob("*.npy"):
                parsed = self._parse_prime_range(path)

                if parsed is None:
                    continue

                start, end = parsed

                try:
                    size_bytes = path.stat().st_size
                except OSError:
                    size_bytes = 0

                records.append(
                    PrimeRangeFile(
                        file_path=path,
                        start=start,
                        end=end,
                        size_bytes=size_bytes,
                    )
                )

        records.sort(key=lambda r: (r.start, r.end, str(r.file_path)))

        return records

    def validate_prime_ranges(self, files: list[PrimeRangeFile]) -> list[str]:
        warnings = []

        if not files:
            warnings.append("No prime files found.")
            return warnings

        for i in range(1, len(files)):
            prev = files[i - 1]
            curr = files[i]

            expected = prev.end + 1

            if curr.start != expected:
                warnings.append(
                    f"Range gap or overlap: "
                    f"{prev.name} ends at {prev.end}, "
                    f"{curr.name} starts at {curr.start}"
                )

        return warnings

    def summary(self) -> None:
        files = self.list_prime_files()

        total_size = sum(f.size_bytes for f in files)

        print("=" * 80)
        print("PrimeNet Repository Service")
        print("=" * 80)

        print("Prime sources:")
        for src in self.prime_sources():
            print(f"  {src}")

        print()
        print(f"Prime files found : {len(files)}")
        print(f"Total size        : {total_size / (1024 ** 3):.6f} GB")

        if files:
            print(f"First range       : {files[0].start} -> {files[0].end}")
            print(f"Last range        : {files[-1].start} -> {files[-1].end}")

        print()
        print("Files:")
        for f in files:
            print(
                f"  {f.start:>15} -> {f.end:<15} "
                f"{f.size_bytes / (1024 ** 3):>8.3f} GB  "
                f"{f.file_path}"
            )

        warnings = self.validate_prime_ranges(files)

        print()
        if warnings:
            print("Validation warnings:")
            for w in warnings:
                print(f"  WARNING: {w}")
        else:
            print("Range validation  : PASSED")

        print("=" * 80)


def main() -> int:
    cfg = Configuration()
    paths = Paths(cfg)
    logger = PrimeNetLogger(cfg, paths)

    repo = Repository(cfg, paths, logger)

    repo.summary()

    return 0


if __name__ == "__main__":
    sys.exit(main())