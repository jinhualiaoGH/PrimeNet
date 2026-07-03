"""
PrimeNet Gap Repository Driver v1.0.0

Builds gap repository from verified prime partitions.

Input:
    E:\\PrimeNet\\Repository\\ranges\\primes_*.npy

Output:
    E:\\PrimeNet\\Repository\\gaps\\gaps_<start>_<end>.npy
    E:\\PrimeNet\\Repository\\metadata\\gap_repository_manifest.csv
    E:\\PrimeNet\\Repository\\logs\\gap_builder_runtime.csv

Run:
    cd C:\\PrimeNet\\Platform
    py -m core.drive_gap_repository
"""

from __future__ import annotations

import csv
import re
import time
from datetime import datetime
from pathlib import Path

import numpy as np


REPOSITORY_ROOT = Path(r"E:\PrimeNet\Repository")

PRIME_DIR = REPOSITORY_ROOT / "ranges"
GAP_DIR = REPOSITORY_ROOT / "gaps"
METADATA_DIR = REPOSITORY_ROOT / "metadata"
LOG_DIR = REPOSITORY_ROOT / "logs"

MANIFEST_CSV = METADATA_DIR / "gap_repository_manifest.csv"
RUNTIME_CSV = LOG_DIR / "gap_builder_runtime.csv"

OVERWRITE = True
VERIFY = True

FILENAME_RE = re.compile(r"primes_(\d+)_(\d+)\.npy$")


def fmt(n: int) -> str:
    return f"{n:,}"


def parse_prime_file(path: Path) -> tuple[int, int]:
    m = FILENAME_RE.match(path.name)
    if not m:
        raise ValueError(f"Invalid prime filename: {path.name}")
    return int(m.group(1)), int(m.group(2))


def list_prime_files() -> list[tuple[int, int, Path]]:
    items = []
    for path in PRIME_DIR.glob("primes_*.npy"):
        start, end = parse_prime_file(path)
        items.append((start, end, path))
    items.sort(key=lambda x: x[0])
    return items


def append_csv(path: Path, fieldnames: list[str], row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()

    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def write_manifest_header() -> None:
    MANIFEST_CSV.parent.mkdir(parents=True, exist_ok=True)

    with MANIFEST_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "gap_file",
                "prime_file",
                "range_start",
                "range_end",
                "prime_count",
                "gap_count",
                "min_gap",
                "max_gap",
                "first_prime",
                "last_prime",
                "next_first_prime_used",
                "file_size_gb",
                "status",
                "created_at",
            ],
        )
        writer.writeheader()


def append_manifest(row: dict) -> None:
    with MANIFEST_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "gap_file",
                "prime_file",
                "range_start",
                "range_end",
                "prime_count",
                "gap_count",
                "min_gap",
                "max_gap",
                "first_prime",
                "last_prime",
                "next_first_prime_used",
                "file_size_gb",
                "status",
                "created_at",
            ],
        )
        writer.writerow(row)


def main() -> None:
    print("=" * 80)
    print("PrimeNet Gap Repository Driver v1.0.0")
    print("=" * 80)

    GAP_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    prime_files = list_prime_files()

    if not prime_files:
        raise RuntimeError(f"No prime files found in {PRIME_DIR}")

    print(f"Prime files : {len(prime_files)}")
    print(f"Prime dir   : {PRIME_DIR}")
    print(f"Gap dir     : {GAP_DIR}")
    print(f"Manifest    : {MANIFEST_CSV}")
    print(f"Runtime log : {RUNTIME_CSV}")
    print(f"Overwrite   : {OVERWRITE}")
    print("=" * 80)

    write_manifest_header()

    total_t0 = time.time()

    for idx, (start, end, prime_path) in enumerate(prime_files, start=1):
        t0 = time.time()

        gap_path = GAP_DIR / f"gaps_{start}_{end}.npy"

        print()
        print("-" * 80)
        print(f"[{idx}/{len(prime_files)}] {fmt(start)} - {fmt(end)}")
        print(f"Prime file: {prime_path}")
        print(f"Gap file  : {gap_path}")
        print("-" * 80)

        if gap_path.exists() and not OVERWRITE:
            print("[SKIP] Gap file already exists.")
            continue

        primes = np.load(prime_path, mmap_mode=None)

        if len(primes) < 2:
            raise RuntimeError(f"Prime file has too few primes: {prime_path}")

        next_first_prime = None

        if idx < len(prime_files):
            next_path = prime_files[idx][2]
            next_primes = np.load(next_path, mmap_mode="r")
            next_first_prime = int(next_primes[0])

            extended = np.empty(len(primes) + 1, dtype=np.uint64)
            extended[:-1] = primes
            extended[-1] = next_first_prime
            gaps = np.diff(extended).astype(np.uint64)
        else:
            gaps = np.diff(primes).astype(np.uint64)

        np.save(gap_path, gaps)

        gap_count = int(len(gaps))
        min_gap = int(gaps.min()) if gap_count else None
        max_gap = int(gaps.max()) if gap_count else None

        if VERIFY:
            reloaded = np.load(gap_path, mmap_mode="r")
            if len(reloaded) != gap_count:
                raise RuntimeError(f"Verification failed for {gap_path}")
            status = "PASSED"
        else:
            status = "WRITTEN"

        file_size_gb = gap_path.stat().st_size / (1024**3)
        runtime_sec = time.time() - t0
        runtime_min = runtime_sec / 60.0

        append_manifest(
            {
                "gap_file": str(gap_path),
                "prime_file": str(prime_path),
                "range_start": start,
                "range_end": end,
                "prime_count": int(len(primes)),
                "gap_count": gap_count,
                "min_gap": min_gap,
                "max_gap": max_gap,
                "first_prime": int(primes[0]),
                "last_prime": int(primes[-1]),
                "next_first_prime_used": next_first_prime,
                "file_size_gb": f"{file_size_gb:.9f}",
                "status": status,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )

        append_csv(
            RUNTIME_CSV,
            fieldnames=[
                "timestamp",
                "batch_id",
                "total_batches",
                "range_start",
                "range_end",
                "prime_count",
                "gap_count",
                "runtime_sec",
                "runtime_min",
                "file_size_gb",
                "status",
            ],
            row={
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "batch_id": idx,
                "total_batches": len(prime_files),
                "range_start": start,
                "range_end": end,
                "prime_count": int(len(primes)),
                "gap_count": gap_count,
                "runtime_sec": f"{runtime_sec:.3f}",
                "runtime_min": f"{runtime_min:.3f}",
                "file_size_gb": f"{file_size_gb:.9f}",
                "status": status,
            },
        )

        print("[SAVED]")
        print(f"Gap count : {gap_count:,}")
        print(f"Min gap   : {min_gap}")
        print(f"Max gap   : {max_gap}")
        print(f"Size      : {file_size_gb:.6f} GB")
        print(f"Runtime   : {runtime_min:.3f} min")
        print(f"Status    : {status}")

    total_runtime_min = (time.time() - total_t0) / 60.0

    print()
    print("=" * 80)
    print("PrimeNet Gap Repository Complete")
    print("=" * 80)
    print(f"Prime files : {len(prime_files)}")
    print(f"Gap files   : {len(list(GAP_DIR.glob('gaps_*.npy')))}")
    print(f"Runtime     : {total_runtime_min:.3f} min")
    print(f"Manifest    : {MANIFEST_CSV}")
    print("=" * 80)


if __name__ == "__main__":
    main()