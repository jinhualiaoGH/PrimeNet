"""
PrimeNet Repository API v1.1.0

Central read-only interface for the PrimeNet prime repository.

Design principle:
    Observatories should not access .npy files directly.
    They should access repository data through PrimeRepository.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Iterator

import numpy as np

from Platform.core.platform_config import load_platform_config
from Platform.core.range_files import (
    RangeFile,
    sorted_range_files,
    validate_adjacency,
)


@dataclass(frozen=True)
class PrimeBlock:
    index: int
    path: Path
    start: int
    end: int
    count: int
    min_prime: int
    max_prime: int
    primes: np.ndarray


def _default_repository_root() -> Path:
    """
    Resolve the configured repository root lazily.

    Importing this module must not read configuration from disk.
    """
    return load_platform_config().paths.repository_root


class PrimeRepository:
    """
    Read-only interface to the canonical PrimeNet prime repository.
    """

    def __init__(
        self,
        repository_root: Path | str | None = None,
    ) -> None:
        if repository_root is None:
            repository_root = _default_repository_root()

        self.repository_root = (
            Path(repository_root)
            .expanduser()
            .resolve()
        )
        self.ranges_dir = self.repository_root / "ranges"
        self.metadata_dir = self.repository_root / "metadata"

        if not self.ranges_dir.is_dir():
            raise FileNotFoundError(
                f"Ranges directory not found: {self.ranges_dir}"
            )

        self._range_files: list[RangeFile] = sorted_range_files(
            self.ranges_dir,
            "primes",
        )

        if not self._range_files:
            raise RuntimeError(
                f"No prime range files found in {self.ranges_dir}"
            )

        adjacency_issues = validate_adjacency(self._range_files)

        if adjacency_issues:
            first_issue = adjacency_issues[0]

            raise ValueError(
                "Prime repository range files are not canonically "
                f"adjacent: {first_issue}"
            )

        self._files: list[Path] = [
            range_file.path
            for range_file in self._range_files
        ]

    def block_count(self) -> int:
        return len(self._range_files)

    def files(self) -> list[Path]:
        return list(self._files)

    def range_files(self) -> list[RangeFile]:
        return list(self._range_files)

    @staticmethod
    def _load_array(
        path: Path,
        mmap_mode: str = "r",
    ) -> np.ndarray:
        """
        Load and validate one canonical prime array.

        The Repository API is intentionally read-only.
        """
        if mmap_mode != "r":
            raise ValueError(
                "PrimeRepository only permits mmap_mode='r'."
            )

        arr = np.load(
            path,
            mmap_mode=mmap_mode,
            allow_pickle=False,
        )

        if arr.ndim != 1:
            raise ValueError(
                f"Prime array is not 1D: {path.name}"
            )

        if arr.shape[0] == 0:
            raise ValueError(
                f"Prime array is empty: {path.name}"
            )

        if not np.issubdtype(arr.dtype, np.integer):
            raise ValueError(
                f"Prime array dtype is not integer: "
                f"{path.name} ({arr.dtype})"
            )

        return arr

    def load_block(
        self,
        index: int,
        mmap_mode: str = "r",
    ) -> PrimeBlock:
        """
        Load one repository block by zero-based index.

        Only read-only memory mapping is permitted.
        """
        if index < 0 or index >= len(self._range_files):
            raise IndexError(
                f"Block index out of range: {index}"
            )

        range_file = self._range_files[index]
        path = range_file.path

        arr = self._load_array(
            path,
            mmap_mode=mmap_mode,
        )

        min_prime = int(arr[0])
        max_prime = int(arr[-1])

        if min_prime < range_file.start:
            raise ValueError(
                f"Prime below filename range in {path.name}: "
                f"{min_prime} < {range_file.start}"
            )

        if max_prime > range_file.end:
            raise ValueError(
                f"Prime above filename range in {path.name}: "
                f"{max_prime} > {range_file.end}"
            )

        return PrimeBlock(
            index=index,
            path=path,
            start=range_file.start,
            end=range_file.end,
            count=int(arr.shape[0]),
            min_prime=min_prime,
            max_prime=max_prime,
            primes=arr,
        )

    def iter_blocks(
        self,
        mmap_mode: str = "r",
    ) -> Iterator[PrimeBlock]:
        """
        Stream repository blocks in canonical numeric order.
        """
        for index in range(len(self._range_files)):
            yield self.load_block(
                index,
                mmap_mode=mmap_mode,
            )

    def iter_primes(self) -> Iterator[int]:
        """
        Stream all primes one by one.

        This is convenient but slower than block-level iteration.
        Use iter_blocks() for large observatory computations.
        """
        for block in self.iter_blocks(mmap_mode="r"):
            for prime in block.primes:
                yield int(prime)

    def total_primes_fast(self) -> int:
        """
        Count total primes from validated array shapes.
        """
        total = 0

        for path in self._files:
            arr = self._load_array(path)
            total += int(arr.shape[0])

        return total

    def boundaries(self) -> list[tuple[int, int, int, int]]:
        """
        Return canonical block boundary information.

        Each tuple:
            (index, start, end, count)
        """
        rows: list[tuple[int, int, int, int]] = []

        for index, range_file in enumerate(self._range_files):
            arr = self._load_array(range_file.path)

            rows.append(
                (
                    index,
                    range_file.start,
                    range_file.end,
                    int(arr.shape[0]),
                )
            )

        return rows

    def summary(self) -> dict[str, object]:
        """
        Return a lightweight repository summary.
        """
        first = self.load_block(0)
        last = self.load_block(
            len(self._range_files) - 1
        )

        return {
            "repository_root": str(self.repository_root),
            "ranges_dir": str(self.ranges_dir),
            "metadata_dir": str(self.metadata_dir),
            "block_count": self.block_count(),
            "first_file": first.path.name,
            "last_file": last.path.name,
            "min_prime": first.min_prime,
            "max_prime": last.max_prime,
        }


def main() -> None:
    repo = PrimeRepository()

    print("=" * 80)
    print("PrimeNet Repository API v1.1.0")
    print("=" * 80)
    print(f"Repository root: {repo.repository_root}")
    print(f"Ranges dir:      {repo.ranges_dir}")
    print(f"Metadata dir:    {repo.metadata_dir}")
    print(f"Block count:     {repo.block_count()}")
    print()

    summary = repo.summary()

    print("Summary")
    print("-" * 80)

    for key, value in summary.items():
        print(f"{key}: {value}")

    print()
    print("First 5 blocks")
    print("-" * 80)

    for block in islice(repo.iter_blocks(), 5):
        print(
            f"[{block.index:03d}] {block.path.name} | "
            f"count={block.count:,} | "
            f"min={block.min_prime:,} | "
            f"max={block.max_prime:,}"
        )

    print()
    print("Repository API loaded successfully.")


if __name__ == "__main__":
    main()