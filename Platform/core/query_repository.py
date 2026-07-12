"""
PrimeNet Query Repository API v1.1.0

Provides fast indexed access to:

    p(i)  = i-th prime
    g(i)  = p(i+1) - p(i)

Run:
    cd C:\\PrimeNet\\Platform
    py -m Platform.core.query_repository
"""

from __future__ import annotations

import bisect
import csv
from collections import OrderedDict
from pathlib import Path
from typing import Any

import numpy as np

from Platform.core.platform_config import load_platform_config
from Platform.core.range_files import sorted_range_files


class PrimeRepository:
    """
    Query interface for the PrimeNet Repository.

    Public API:
        summary()
        prime(i)
        gap(i)
        primes(i, length)
        gaps(i, length)
        floor_prime(n)
        ceiling_prime(n)
        partition_for_n(n)
        partition_for_index(i)
    """

    def __init__(
        self,
        root: str | Path | None = None,
        cache_size: int = 4,
    ) -> None:
        config = load_platform_config()
        paths = config.paths

        self.root = (
            Path(root).expanduser().resolve()
            if root is not None
            else paths.repository_root
        )

        if root is None:
            self.prime_dir = paths.ranges_dir
            self.metadata_dir = paths.metadata_dir
        else:
            self.prime_dir = self.root / "ranges"
            self.metadata_dir = self.root / "metadata"

        self.gap_dir = paths.gaps_dir if root is None else self.root / "gaps_u16_v3"

        self.prime_manifest = self.metadata_dir / "repository_manifest.csv"
        self.gap_manifest = (
            self.metadata_dir
            / "gap_repository_u16_v3_manifest.csv"
        )

        self.cache_size = cache_size
        self._prime_cache: OrderedDict[int, np.ndarray] = OrderedDict()
        self._gap_cache: OrderedDict[int, np.ndarray] = OrderedDict()

        self.partitions = self._load_prime_partitions()
        self.gap_partitions = self._load_gap_partitions()

        if not self.partitions:
            raise RuntimeError(f"No prime partitions found in {self.prime_dir}")

        self.range_starts = [p["range_start"] for p in self.partitions]
        self.range_ends = [p["range_end"] for p in self.partitions]

        self.prime_counts = [p["prime_count"] for p in self.partitions]

        self.cumulative_counts = []
        total = 0
        for count in self.prime_counts:
            self.cumulative_counts.append(total)
            total += count

        self.total_primes = total
        self.range_start = self.partitions[0]["range_start"]
        self.range_end = self.partitions[-1]["range_end"]

    # ------------------------------------------------------------------
    # Manifest loading
    # ------------------------------------------------------------------

    def _load_prime_partitions(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        if self.prime_manifest.exists():
            with self.prime_manifest.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    start = self._first_int(row, ["range_start", "start", "batch_start"])
                    end = self._first_int(row, ["range_end", "end", "batch_end"])

                    if start is None or end is None:
                        continue

                    path = self._first_path(
                        row,
                        ["file", "filename", "output_file", "path"],
                        default=self.prime_dir / f"primes_{start}_{end}.npy",
                    )

                    if not path.exists():
                        path = self.prime_dir / f"primes_{start}_{end}.npy"

                    if not path.exists():
                        continue

                    count = self._first_int(row, ["prime_count", "count", "primes"])
                    if count is None:
                        count = int(len(np.load(path, mmap_mode="r")))

                    rows.append(
                        {
                            "range_start": start,
                            "range_end": end,
                            "path": path,
                            "prime_count": count,
                        }
                    )

        if not rows:
            for range_file in sorted_range_files(self.prime_dir, "primes"):
                path = range_file.path
                start = range_file.start
                end = range_file.end

                count = int(len(np.load(path, mmap_mode="r")))

                rows.append(
                    {
                        "range_start": start,
                        "range_end": end,
                        "path": path,
                        "prime_count": count,
                    }
                )

        rows.sort(key=lambda r: r["range_start"])
        return rows

    def _load_gap_partitions(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        if self.gap_manifest.exists():
            with self.gap_manifest.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    start = self._first_int(row, ["range_start", "start"])
                    end = self._first_int(row, ["range_end", "end"])

                    if start is None or end is None:
                        continue

                    filename = row.get("filename")
                    if filename:
                        path = self.gap_dir / filename
                    else:
                        path = self.gap_dir / f"gaps_{start}_{end}.npy"

                    if not path.exists():
                        continue

                    gap_count = self._first_int(row, ["gap_count", "count"])
                    if gap_count is None:
                        gap_count = int(len(np.load(path, mmap_mode="r")))

                    max_gap = self._first_int(row, ["max_gap"])

                    rows.append(
                        {
                            "range_start": start,
                            "range_end": end,
                            "path": path,
                            "gap_count": gap_count,
                            "max_gap": max_gap,
                        }
                    )

        if not rows:
            for range_file in sorted_range_files(self.gap_dir, "gaps"):
                path = range_file.path
                start = range_file.start
                end = range_file.end

                arr = np.load(path, mmap_mode="r")

                rows.append(
                    {
                        "range_start": start,
                        "range_end": end,
                        "path": path,
                        "gap_count": int(len(arr)),
                        "max_gap": int(arr.max()) if len(arr) else None,
                    }
                )

        rows.sort(key=lambda r: r["range_start"])
        return rows

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _first_int(row: dict[str, Any], keys: list[str]) -> int | None:
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                try:
                    return int(float(value))
                except Exception:
                    pass
        return None

    @staticmethod
    def _first_path(
        row: dict[str, Any],
        keys: list[str],
        default: Path,
    ) -> Path:
        for key in keys:
            value = row.get(key)
            if value:
                path = Path(value)
                return path if path.is_absolute() else default.parent / value
        return default

    @staticmethod
    def _parse_range_filename(path: Path, prefix: str) -> tuple[int, int]:
        stem = path.stem
        if not stem.startswith(prefix):
            raise ValueError(f"Invalid filename: {path.name}")
        a, b = stem.replace(prefix, "", 1).split("_")
        return int(a), int(b)

    def _cached_load(
        self,
        cache: OrderedDict[int, np.ndarray],
        idx: int,
        path: Path,
    ) -> np.ndarray:
        if idx in cache:
            arr = cache.pop(idx)
            cache[idx] = arr
            return arr

        arr = np.load(path, mmap_mode="r")
        cache[idx] = arr

        while len(cache) > self.cache_size:
            cache.popitem(last=False)

        return arr

    def _prime_array(self, idx: int) -> np.ndarray:
        return self._cached_load(self._prime_cache, idx, self.partitions[idx]["path"])

    def _gap_array(self, idx: int) -> np.ndarray:
        return self._cached_load(self._gap_cache, idx, self.gap_partitions[idx]["path"])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "prime_partitions": len(self.partitions),
            "gap_partitions": len(self.gap_partitions),
            "total_primes": self.total_primes,
            "range_start": self.range_start,
            "range_end": self.range_end,
            "prime_dtype": "uint64",
            "gap_dtype": "uint16",
            "cache_size": self.cache_size,
        }

    def partition_for_n(self, n: int) -> dict[str, Any]:
        idx = bisect.bisect_right(self.range_starts, n) - 1

        if idx < 0 or n > self.range_ends[idx]:
            raise ValueError(f"n={n} is outside repository range")

        return self.partitions[idx]

    def partition_index_for_n(self, n: int) -> int:
        idx = bisect.bisect_right(self.range_starts, n) - 1

        if idx < 0 or n > self.range_ends[idx]:
            raise ValueError(f"n={n} is outside repository range")

        return idx

    def partition_for_index(self, i: int) -> tuple[int, int]:
        if i < 1 or i > self.total_primes:
            raise ValueError(f"prime index i={i} is outside repository range")

        idx = bisect.bisect_right(self.cumulative_counts, i - 1) - 1
        local = (i - 1) - self.cumulative_counts[idx]

        return idx, local

    def prime(self, i: int) -> int:
        idx, local = self.partition_for_index(i)
        arr = self._prime_array(idx)
        return int(arr[local])

    def gap(self, i: int) -> int:
        idx, local = self.partition_for_index(i)

        if idx >= len(self.gap_partitions):
            raise ValueError(f"No gap partition exists for index i={i}")

        arr = self._gap_array(idx)

        if local >= len(arr):
            raise ValueError(f"No gap available for index i={i}")

        return int(arr[local])

    def primes(self, i: int, length: int) -> np.ndarray:
        if length <= 0:
            return np.array([], dtype=np.uint64)

        if i < 1:
            raise ValueError("i must be >= 1")

        if i + length - 1 > self.total_primes:
            raise ValueError("prime window exceeds repository range")

        result = np.empty(length, dtype=np.uint64)

        written = 0
        current_i = i

        while written < length:
            idx, local = self.partition_for_index(current_i)
            arr = self._prime_array(idx)

            take = min(length - written, len(arr) - local)
            result[written : written + take] = arr[local : local + take]

            written += take
            current_i += take

        return result

    def gaps(self, i: int, length: int) -> np.ndarray:
        if length <= 0:
            return np.array([], dtype=np.uint16)

        if i < 1:
            raise ValueError("i must be >= 1")

        if i + length - 1 > self.total_primes - 1:
            raise ValueError("gap window exceeds repository range")

        result = np.empty(length, dtype=np.uint16)

        written = 0
        current_i = i

        while written < length:
            idx, local = self.partition_for_index(current_i)

            if idx >= len(self.gap_partitions):
                raise ValueError(f"No gap partition exists for index i={current_i}")

            arr = self._gap_array(idx)

            take = min(length - written, len(arr) - local)
            result[written : written + take] = arr[local : local + take]

            written += take
            current_i += take

        return result

    def floor_prime(self, n: int) -> int | None:
        if n < self.range_start:
            return None

        if n > self.range_end:
            idx = len(self.partitions) - 1
        else:
            idx = self.partition_index_for_n(n)

        arr = self._prime_array(idx)
        pos = np.searchsorted(arr, n, side="right") - 1

        if pos >= 0:
            return int(arr[pos])

        if idx == 0:
            return None

        prev_arr = self._prime_array(idx - 1)
        return int(prev_arr[-1])

    def ceiling_prime(self, n: int) -> int | None:
        if n > self.range_end:
            return None

        if n < self.range_start:
            idx = 0
        else:
            idx = self.partition_index_for_n(n)

        arr = self._prime_array(idx)
        pos = np.searchsorted(arr, n, side="left")

        if pos < len(arr):
            return int(arr[pos])

        if idx + 1 >= len(self.partitions):
            return None

        next_arr = self._prime_array(idx + 1)
        return int(next_arr[0])

    def contains_prime(self, n: int) -> bool:
        p = self.floor_prime(n)
        return p == n

    def gap_after_prime_index(self, i: int) -> int:
        return self.gap(i)


def main() -> None:
    config = load_platform_config()
    repo = PrimeRepository()

    print("=" * 80)
    print("PrimeNet Query Repository API v1.1.0")
    print("=" * 80)

    print(repo.summary())

    print()
    print("Sample Queries")
    print("-" * 80)

    for i in [1, 2, 3, 10, 1_000_000]:
        print(f"p({i}) = {repo.prime(i)}")

    for i in [1, 2, 3, 10, 1_000_000]:
        print(f"g({i}) = {repo.gap(i)}")

    n = load_platform_config().campaign.start

    print()
    print(f"floor_prime({n})   = {repo.floor_prime(n)}")
    print(f"ceiling_prime({n}) = {repo.ceiling_prime(n)}")
    print(f"contains_prime({n}) = {repo.contains_prime(n)}")

    print()
    print("Window sample")
    print("-" * 80)

    ps = repo.primes(1_000_000, 10)
    gs = repo.gaps(1_000_000, 10)

    print("primes:", ps)
    print("gaps:  ", gs)

    print("=" * 80)


if __name__ == "__main__":
    main()