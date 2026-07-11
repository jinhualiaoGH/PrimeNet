"""
PrimeNet Direct Gap Repository Builder v3.0.0

Left-owned full-mode gap repository.

Invariant:
    one stored prime p(i) -> one stored outgoing gap g(i)

For ordinary files:
    final gap uses first prime of next file.

For terminal repository file:
    final gap uses direct next-prime computation.
"""

from __future__ import annotations

import csv
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from core.range_files import sorted_range_files


VERSION = "3.0.0"

from core.platform_config import load_platform_config


CONFIG = load_platform_config()
PATHS = CONFIG.paths

REPOSITORY_ROOT = PATHS.repository_root
PRIME_DIR = PATHS.ranges_dir

# Canonical index-aligned uint16 gap repository.
OUT_DIR = PATHS.gaps_dir

METADATA_DIR = PATHS.metadata_dir
LOG_DIR = PATHS.logs_dir

MANIFEST_CSV = METADATA_DIR / "gap_repository_u16_v3_manifest.csv"
RUNTIME_CSV = LOG_DIR / "gap_u16_v3_runtime.csv"

OVERWRITE = True
VERIFY = True
MAX_UINT16 = np.iinfo(np.uint16).max


def fmt(n: int) -> str:
    return f"{n:,}"


def append_csv(path: Path, fieldnames: list[str], row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()

    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def reset_manifest() -> None:
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    if MANIFEST_CSV.exists():
        MANIFEST_CSV.unlink()


def is_prime_trial_division(n: int) -> bool:
    """
    Deterministic enough here because terminal next-prime search near 3T
    only tests a very small number of candidates.
    """
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False

    d = 3
    while d * d <= n:
        if n % d == 0:
            return False
        d += 2

    return True


def next_prime_after(n: int) -> int:
    """
    Compute the next prime strictly greater than n.
    Used only for the terminal repository boundary.
    """
    candidate = n + 1

    if candidate <= 2:
        return 2

    if candidate % 2 == 0:
        candidate += 1

    while not is_prime_trial_division(candidate):
        candidate += 2

    return candidate


def build_gap_partition(
    prime_path: Path,
    next_prime_path: Path | None,
    out_path: Path,
) -> dict:
    primes = np.load(prime_path, mmap_mode=None)

    if primes.ndim != 1:
        raise RuntimeError(f"Expected 1D prime array: {prime_path}")

    if len(primes) < 2:
        raise RuntimeError(f"Too few primes in {prime_path}")

    prime_count = len(primes)
    gaps = np.empty(prime_count, dtype=np.uint16)

    local_diffs = primes[1:] - primes[:-1]
    max_local = int(local_diffs.max()) if len(local_diffs) else 0

    if next_prime_path is not None:
        next_primes = np.load(next_prime_path, mmap_mode="r")
        next_first_prime = int(next_primes[0])
        terminal_next_prime_computed = False
    else:
        next_first_prime = next_prime_after(int(primes[-1]))
        terminal_next_prime_computed = True

    boundary_gap = next_first_prime - int(primes[-1])
    max_gap = max(max_local, boundary_gap)

    if max_gap > MAX_UINT16:
        raise RuntimeError(f"max_gap={max_gap} exceeds uint16 capacity")

    gaps[:-1] = local_diffs.astype(np.uint16)
    gaps[-1] = np.uint16(boundary_gap)

    min_gap = int(gaps.min())
    max_gap_final = int(gaps.max())

    np.save(out_path, gaps)

    if VERIFY:
        reloaded = np.load(out_path, mmap_mode="r")

        if len(reloaded) != len(primes):
            raise RuntimeError(f"Length mismatch after save: {out_path}")

        if int(reloaded[-1]) != boundary_gap:
            raise RuntimeError(f"Boundary gap mismatch after save: {out_path}")

        if int(reloaded.max()) != max_gap_final:
            raise RuntimeError(f"Max gap mismatch after save: {out_path}")

    return {
        "prime_count": int(prime_count),
        "gap_count": int(len(gaps)),
        "min_gap": min_gap,
        "max_gap": max_gap_final,
        "first_prime": int(primes[0]),
        "last_prime": int(primes[-1]),
        "next_prime_used": int(next_first_prime),
        "boundary_gap": int(boundary_gap),
        "terminal_next_prime_computed": terminal_next_prime_computed,
    }


def main() -> None:
    print("=" * 80)
    print(f"PrimeNet Direct Gap Repository Builder v{VERSION}")
    print("=" * 80)
    print("Mode       : left-owned full mode")
    print("Rule       : repository order is numeric coordinate order")
    print("Invariant  : prime_count == gap_count for every file")
    print("=" * 80)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    reset_manifest()

    prime_files = sorted_range_files(PRIME_DIR, "primes")

    if not prime_files:
        raise RuntimeError(f"No prime files found in {PRIME_DIR}")

    print(f"Prime files : {len(prime_files)}")
    print(f"Prime dir   : {PRIME_DIR}")
    print(f"Output dir  : {OUT_DIR}")
    print(f"Manifest    : {MANIFEST_CSV}")
    print(f"Runtime log : {RUNTIME_CSV}")
    print(f"Overwrite   : {OVERWRITE}")
    print("=" * 80)

    total_t0 = time.time()
    total_size_gb = 0.0

    manifest_fields = [
        "gap_file",
        "prime_file",
        "range_start",
        "range_end",
        "dtype",
        "prime_count",
        "gap_count",
        "min_gap",
        "max_gap",
        "first_prime",
        "last_prime",
        "next_prime_used",
        "boundary_gap",
        "terminal_next_prime_computed",
        "file_size_gb",
        "runtime_min",
        "status",
        "created_at",
    ]

    runtime_fields = [
        "timestamp",
        "batch_id",
        "total_batches",
        "range_start",
        "range_end",
        "runtime_sec",
        "runtime_min",
        "file_size_gb",
        "max_gap",
        "boundary_gap",
        "terminal_next_prime_computed",
        "status",
    ]

    for idx, rf in enumerate(prime_files, start=1):
        t0 = time.time()

        out_path = OUT_DIR / f"gaps_{rf.start}_{rf.end}.npy"
        next_prime_path = prime_files[idx].path if idx < len(prime_files) else None

        print()
        print("-" * 80)
        print(f"[{idx}/{len(prime_files)}] {fmt(rf.start)} - {fmt(rf.end)}")
        print(f"Prime file: {rf.path}")
        print(f"Gap file  : {out_path}")
        print("-" * 80)

        if out_path.exists() and not OVERWRITE:
            print("[SKIP] Existing output found.")
            continue

        stats = build_gap_partition(rf.path, next_prime_path, out_path)

        runtime_sec = time.time() - t0
        runtime_min = runtime_sec / 60.0
        file_size_gb = out_path.stat().st_size / (1024**3)
        total_size_gb += file_size_gb

        append_csv(
            MANIFEST_CSV,
            manifest_fields,
            {
                "gap_file": str(out_path),
                "prime_file": str(rf.path),
                "range_start": rf.start,
                "range_end": rf.end,
                "dtype": "uint16",
                "prime_count": stats["prime_count"],
                "gap_count": stats["gap_count"],
                "min_gap": stats["min_gap"],
                "max_gap": stats["max_gap"],
                "first_prime": stats["first_prime"],
                "last_prime": stats["last_prime"],
                "next_prime_used": stats["next_prime_used"],
                "boundary_gap": stats["boundary_gap"],
                "terminal_next_prime_computed": stats["terminal_next_prime_computed"],
                "file_size_gb": f"{file_size_gb:.9f}",
                "runtime_min": f"{runtime_min:.3f}",
                "status": "PASSED",
                "created_at": datetime.now().isoformat(timespec="seconds"),
            },
        )

        append_csv(
            RUNTIME_CSV,
            runtime_fields,
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "batch_id": idx,
                "total_batches": len(prime_files),
                "range_start": rf.start,
                "range_end": rf.end,
                "runtime_sec": f"{runtime_sec:.3f}",
                "runtime_min": f"{runtime_min:.3f}",
                "file_size_gb": f"{file_size_gb:.9f}",
                "max_gap": stats["max_gap"],
                "boundary_gap": stats["boundary_gap"],
                "terminal_next_prime_computed": stats["terminal_next_prime_computed"],
                "status": "PASSED",
            },
        )

        print("[SAVED]")
        print(f"Gap count : {stats['gap_count']:,}")
        print(f"Min gap   : {stats['min_gap']}")
        print(f"Max gap   : {stats['max_gap']}")
        print(f"Boundary  : {stats['boundary_gap']}")
        print(f"Terminal  : {stats['terminal_next_prime_computed']}")
        print(f"Size      : {file_size_gb:.6f} GB")
        print(f"Runtime   : {runtime_min:.3f} min")
        print("Status    : PASSED")

    total_runtime_min = (time.time() - total_t0) / 60.0

    print()
    print("=" * 80)
    print("PrimeNet Direct Gap Repository v3 Complete")
    print("=" * 80)
    print(f"Files       : {len(prime_files)}")
    print(f"Output size : {total_size_gb:.6f} GB")
    print(f"Runtime     : {total_runtime_min:.3f} min")
    print(f"Manifest    : {MANIFEST_CSV}")
    print("=" * 80)


if __name__ == "__main__":
    main()
