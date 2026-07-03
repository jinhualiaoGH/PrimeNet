"""
PrimeNet Query Repository API v1.0.0

Run:
    cd C:\\PrimeNet\\Platform
    py -m core.query_repository
"""

from __future__ import annotations

import csv
import bisect
from pathlib import Path

import numpy as np


class PrimeRepository:
    def __init__(self, root: str | Path = r"E:\PrimeNet\Repository") -> None:
        self.root = Path(root)
        self.prime_dir = self.root / "ranges"
        self.gap_dir = self.root / "gaps_u16"
        self.metadata_dir = self.root / "metadata"

        self.manifest_path = self.metadata_dir / "repository_manifest.csv"
        self.gap_manifest_path = self.metadata_dir / "gap_repository_u16_manifest.csv"

        self.partitions = self._load_prime_partitions()
        self.gap_partitions = self._load_gap_partitions()

        self.starts = [p["range_start"] for p in self.partitions]
        self.ends = [p["range_end"] for p in self.partitions]

        self.prime_counts = [p["prime_count"] for p in self.partitions]
        self.cumulative_counts = []
        total = 0
        for c in self.prime_counts:
            self.cumulative_counts.append(total)
            total += c
        self.total_primes = total

    def _load_prime_partitions(self) -> list[dict]:
        rows: list[dict] = []

        # Prefer manifest if available.
        if self.manifest_path.exists():
            with self.manifest_path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        start = int(row.get("range_start") or row.get("start"))
                        end = int(row.get("range_end") or row.get("end"))
                    except Exception:
                        continue

                    filename = (
                        row.get("file")
                        or row.get("filename")
                        or row.get("output_file")
                        or row.get("path")
                    )

                    if filename:
                        path = Path(filename)
                        if not path.is_absolute():
                            path = self.prime_dir / filename
                    else:
                        path = self.prime_dir / f"primes_{start}_{end}.npy"

                    if not path.exists():
                        path = self.prime_dir / f"primes_{start}_{end}.npy"

                    count = row.get("count") or row.get("prime_count")
                    if count is None:
                        count = len(np.load(path, mmap_mode="r"))

                    rows.append(
                        {
                            "range_start": start,
                            "range_end": end,
                            "path": path,
                            "prime_count": int(count),
                        }
                    )

        # Fallback from filenames.
        if not rows:
            for path in self.prime_dir.glob("primes_*.npy"):
                name = path.stem.replace("primes_", "")
                a, b = name.split("_")
                start = int(a)
                end = int(b)
                count = len(np.load(path, mmap_mode="r"))
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

    def _load_gap_partitions(self) -> list[dict]:
        rows: list[dict] = []

        if self.gap_manifest_path.exists():
            with self.gap_manifest_path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        start = int(row["range_start"])
                        end = int(row["range_end"])
                    except Exception:
                        continue

                    filename = row.get("filename")
                    path = self.gap_dir / filename if filename else self.gap_dir / f"gaps_{start}_{end}.npy"

                    rows.append(
                        {
                            "range_start": start,
                            "range_end": end,
                            "path": path,
                            "gap_count": int(row.get("gap_count", 0)),
                            "max_gap": int(row.get("max_gap", 0)),
                        }
                    )

        if not rows:
            for path in self.gap_dir.glob("gaps_*.npy"):
                name = path.stem.replace("gaps_", "")
                a, b = name.split("_")
                start = int(a)
                end = int(b)
                rows.append(
                    {
                        "range_start": start,
                        "range_end": end,
                        "path": path,
                        "gap_count": len(np.load(path, mmap_mode="r")),
                        "max_gap": int(np.load(path, mmap_mode="r").max()),
                    }
                )

        rows.sort(key=lambda r: r["range_start"])
        return rows

    def summary(self) -> dict:
        return {
            "root": str(self.root),
            "prime_partitions": len(self.partitions),
            "gap_partitions": len(self.gap_partitions),
            "total_primes": self.total_primes,
            "range_start": self.partitions[0]["range_start"],
            "range_end": self.partitions[-1]["range_end"],
        }

    def partition_for_n(self, n: int) -> dict:
        idx = bisect.bisect_right(self.starts, n) - 1
        if idx < 0 or n > self.ends[idx]:
            raise ValueError(f"n={n} is outside repository range")
        return self.partitions[idx]

    def partition_for_index(self, i: int) -> tuple[int, int]:
        if i < 1 or i > self.total_primes:
            raise ValueError(f"prime index i={i} is outside repository range")

        idx = bisect.bisect_right(self.cumulative_counts, i - 1) - 1
        local = (i - 1) - self.cumulative_counts[idx]
        return idx, local

    def prime(self, i: int) -> int:
        idx, local = self.partition_for_index(i)
        arr = np.load(self.partitions[idx]["path"], mmap_mode="r")
        return int(arr[local])

    def gap(self, i: int) -> int:
        idx, local = self.partition_for_index(i)

        if idx >= len(self.gap_partitions):
            raise ValueError(f"No gap partition for index {i}")

        arr = np.load(self.gap_partitions[idx]["path"], mmap_mode="r")

        if local >= len(arr):
            raise ValueError(f"No gap available at index {i}")

        return int(arr[local])

    def floor_prime(self, n: int) -> int | None:
        part = self.partition_for_n(n)
        arr = np.load(part["path"], mmap_mode="r")
        pos = np.searchsorted(arr, n, side="right") - 1
        if pos >= 0:
            return int(arr[pos])

        idx = self.partitions.index(part)
        if idx == 0:
            return None

        prev = np.load(self.partitions[idx - 1]["path"], mmap_mode="r")
        return int(prev[-1])

    def ceiling_prime(self, n: int) -> int | None:
        part = self.partition_for_n(n)
        arr = np.load(part["path"], mmap_mode="r")
        pos = np.searchsorted(arr, n, side="left")
        if pos < len(arr):
            return int(arr[pos])

        idx = self.partitions.index(part)
        if idx + 1 >= len(self.partitions):
            return None

        nxt = np.load(self.partitions[idx + 1]["path"], mmap_mode="r")
        return int(nxt[0])

    def primes(self, i: int, length: int) -> np.ndarray:
        values = [self.prime(j) for j in range(i, i + length)]
        return np.array(values, dtype=np.uint64)

    def gaps(self, i: int, length: int) -> np.ndarray:
        values = [self.gap(j) for j in range(i, i + length)]
        return np.array(values, dtype=np.uint16)


def main() -> None:
    repo = PrimeRepository()

    print("=" * 80)
    print("PrimeNet Query Repository API v1.0.0")
    print("=" * 80)

    print(repo.summary())

    print()
    print("Sample Queries")
    print("-" * 80)

    for i in [1, 2, 3, 10, 1_000_000]:
        print(f"p({i}) = {repo.prime(i)}")

    for i in [1, 2, 3, 10, 1_000_000]:
        print(f"g({i}) = {repo.gap(i)}")

    n = 1_000_000_000_000
    print()
    print(f"floor_prime({n})   = {repo.floor_prime(n)}")
    print(f"ceiling_prime({n}) = {repo.ceiling_prime(n)}")

    print("=" * 80)


if __name__ == "__main__":
    main()