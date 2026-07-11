"""
PrimeNet Repository API

Central read-only interface for the PrimeNet prime repository.

Design principle:
    Observatories should not access .npy files directly.
    They should access repository data through PrimeRepository.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

import numpy as np


DEFAULT_REPOSITORY_ROOT = Path(r"E:\PrimeNet\Repository")


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


class PrimeRepository:
    """
    Read-only interface to the PrimeNet repository.
    """

    def __init__(self, repository_root: Path | str = DEFAULT_REPOSITORY_ROOT):
        self.repository_root = Path(repository_root)
        self.ranges_dir = self.repository_root / "ranges"
        self.metadata_dir = self.repository_root / "metadata"

        if not self.ranges_dir.exists():
            raise FileNotFoundError(f"Ranges directory not found: {self.ranges_dir}")

        self._files = self._find_range_files()

        if not self._files:
            raise RuntimeError(f"No prime range files found in {self.ranges_dir}")

    def _parse_range_from_name(self, path: Path) -> tuple[int, int]:
        """
        Expected filename format:
            primes_START_END.npy
        """
        stem = path.stem
        parts = stem.split("_")

        if len(parts) != 3 or parts[0] != "primes":
            raise ValueError(f"Invalid range filename: {path.name}")

        return int(parts[1]), int(parts[2])

    def _find_range_files(self) -> list[Path]:
        files = list(self.ranges_dir.glob("primes_*.npy"))
        files.sort(key=self._parse_range_from_name)
        return files

    def block_count(self) -> int:
        return len(self._files)

    def files(self) -> list[Path]:
        return list(self._files)

    def load_block(self, index: int, mmap_mode: str = "r") -> PrimeBlock:
        """
        Load one repository block by zero-based index.

        Default mmap_mode="r" keeps the file read-only.
        """
        if index < 0 or index >= len(self._files):
            raise IndexError(f"Block index out of range: {index}")

        path = self._files[index]
        start, end = self._parse_range_from_name(path)

        arr = np.load(path, mmap_mode=mmap_mode)

        if arr.ndim != 1:
            raise ValueError(f"Array is not 1D: {path.name}")

        if arr.shape[0] == 0:
            raise ValueError(f"Array is empty: {path.name}")

        return PrimeBlock(
            index=index,
            path=path,
            start=start,
            end=end,
            count=int(arr.shape[0]),
            min_prime=int(arr[0]),
            max_prime=int(arr[-1]),
            primes=arr,
        )

    def iter_blocks(self, mmap_mode: str = "r") -> Iterator[PrimeBlock]:
        """
        Stream all repository blocks in numeric order.
        """
        for i in range(len(self._files)):
            yield self.load_block(i, mmap_mode=mmap_mode)

    def iter_primes(self) -> Iterator[int]:
        """
        Stream all primes one by one.

        This is convenient but slower than block-level iteration.
        Use iter_blocks() for large observatory computations.
        """
        for block in self.iter_blocks(mmap_mode="r"):
            for p in block.primes:
                yield int(p)

    def total_primes_fast(self) -> int:
        """
        Count total primes by reading array shapes only.
        """
        total = 0
        for path in self._files:
            arr = np.load(path, mmap_mode="r")
            total += int(arr.shape[0])
        return total

    def boundaries(self) -> list[tuple[int, int, int, int]]:
        """
        Return block boundary information.

        Each tuple:
            (index, start, end, count)
        """
        rows = []
        for i, path in enumerate(self._files):
            start, end = self._parse_range_from_name(path)
            arr = np.load(path, mmap_mode="r")
            rows.append((i, start, end, int(arr.shape[0])))
        return rows

    def summary(self) -> dict:
        """
        Lightweight repository summary.
        """
        first = self.load_block(0)
        last = self.load_block(len(self._files) - 1)

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
    print("PrimeNet Repository API")
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

    for block in list(repo.iter_blocks())[:5]:
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