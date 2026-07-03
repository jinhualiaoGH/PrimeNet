"""
PrimeNet Repository Builder
===========================

Official Stage 1 instrument for building one prime range file.

Example:
    py -m core.build_prime_range --start 1 --end 10000000000 --overwrite

Output:
    E:\\PrimeNet\\Repository\\ranges\\primes_START_END.npy
"""

from __future__ import annotations

import argparse
import csv
import math
import time
from datetime import datetime
from pathlib import Path

import numpy as np


# =============================================================================
# Default repository configuration
# =============================================================================

REPOSITORY_ROOT = Path(r"E:\PrimeNet\Repository")
RANGES_DIR = REPOSITORY_ROOT / "ranges"
METADATA_DIR = REPOSITORY_ROOT / "metadata"
LOGS_DIR = REPOSITORY_ROOT / "logs"

MANIFEST_FILE = METADATA_DIR / "repository_manifest.csv"
COUNTS_FILE = METADATA_DIR / "prime_counts.csv"
RUNTIME_LOG_FILE = LOGS_DIR / "builder_runtime.csv"

DEFAULT_SEGMENT_SIZE = 50_000_000
DEFAULT_PROGRESS_STEP = 10


# =============================================================================
# Utility
# =============================================================================

def format_int(n: int) -> str:
    return f"{n:,}"


def ensure_dirs() -> None:
    RANGES_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def output_path(start: int, end: int) -> Path:
    return RANGES_DIR / f"primes_{start}_{end}.npy"


def now_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# =============================================================================
# Prime generation
# =============================================================================

def simple_sieve(limit: int) -> np.ndarray:
    """
    Generate all primes <= limit using a standard sieve.
    """
    if limit < 2:
        return np.array([], dtype=np.uint64)

    sieve = np.ones(limit + 1, dtype=bool)
    sieve[:2] = False

    root = int(math.isqrt(limit))
    for p in range(2, root + 1):
        if sieve[p]:
            sieve[p * p : limit + 1 : p] = False

    return np.nonzero(sieve)[0].astype(np.uint64)


def segmented_primes(start: int, end: int, segment_size: int, progress_step: int) -> np.ndarray:
    """
    Generate primes in [start, end] using segmented sieve.
    """
    if start < 1:
        raise ValueError("start must be >= 1")
    if end < start:
        raise ValueError("end must be >= start")

    base_limit = int(math.isqrt(end)) + 1
    base_primes = simple_sieve(base_limit)

    total_numbers = end - start + 1
    total_segments = math.ceil(total_numbers / segment_size)

    primes_chunks: list[np.ndarray] = []

    next_progress = progress_step

    for seg_index, low in enumerate(range(start, end + 1, segment_size), start=1):
        high = min(low + segment_size - 1, end)

        segment = np.ones(high - low + 1, dtype=bool)

        for p in base_primes:
            pp = int(p)
            if pp * pp > high:
                break

            first = max(pp * pp, ((low + pp - 1) // pp) * pp)
            segment[first - low : high - low + 1 : pp] = False

        if low == 1:
            segment[0] = False
            if high >= 2:
                segment[1] = True

        elif low == 2:
            segment[0] = True

        primes = np.nonzero(segment)[0].astype(np.uint64) + np.uint64(low)
        primes_chunks.append(primes)

        progress = 100.0 * seg_index / total_segments

        if progress >= next_progress or seg_index == total_segments:
            primes_so_far = sum(len(x) for x in primes_chunks)
            print(
                f"[PROGRESS] {progress:6.2f}% "
                f"({seg_index}/{total_segments} segments) "
                f"current={format_int(low)}-{format_int(high)} "
                f"primes_so_far={format_int(primes_so_far)}"
            )
            while next_progress <= progress:
                next_progress += progress_step

    if not primes_chunks:
        return np.array([], dtype=np.uint64)

    return np.concatenate(primes_chunks)


# =============================================================================
# Verification
# =============================================================================

def verify_prime_array(arr: np.ndarray, start: int, end: int) -> dict:
    """
    Lightweight structural verification.
    """
    result = {
        "passed": False,
        "count": int(len(arr)),
        "min_prime": None,
        "max_prime": None,
        "strictly_increasing": True,
        "within_range": True,
        "dtype": str(arr.dtype),
    }

    if len(arr) == 0:
        result["passed"] = True
        return result

    result["min_prime"] = int(arr[0])
    result["max_prime"] = int(arr[-1])

    result["strictly_increasing"] = bool(np.all(arr[1:] > arr[:-1]))
    result["within_range"] = bool(arr[0] >= start and arr[-1] <= end)

    result["passed"] = (
        result["strictly_increasing"]
        and result["within_range"]
        and arr.dtype == np.uint64
    )

    return result


# =============================================================================
# Metadata logging
# =============================================================================

def append_csv(path: Path, row: dict, fieldnames: list[str]) -> None:
    exists = path.exists()

    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not exists:
            writer.writeheader()

        writer.writerow(row)


def update_manifest(row: dict) -> None:
    fieldnames = [
        "timestamp",
        "start",
        "end",
        "filename",
        "count",
        "min_prime",
        "max_prime",
        "size_bytes",
        "size_gb",
        "verify_passed",
    ]
    append_csv(MANIFEST_FILE, row, fieldnames)


def update_counts(row: dict) -> None:
    fieldnames = [
        "timestamp",
        "start",
        "end",
        "count",
        "min_prime",
        "max_prime",
    ]
    append_csv(COUNTS_FILE, row, fieldnames)


def log_runtime(row: dict) -> None:
    fieldnames = [
        "timestamp",
        "start",
        "end",
        "segment_size",
        "count",
        "generate_sec",
        "save_sec",
        "verify_sec",
        "total_sec",
        "total_min",
        "size_bytes",
        "size_gb",
        "status",
    ]
    append_csv(RUNTIME_LOG_FILE, row, fieldnames)


# =============================================================================
# Main builder
# =============================================================================

def build_range(
    start: int,
    end: int,
    segment_size: int,
    progress_step: int,
    overwrite: bool,
    skip_existing: bool,
) -> None:
    ensure_dirs()

    out_file = output_path(start, end)

    print("=" * 80)
    print("PrimeNet Repository Builder v1.2.0")
    print("=" * 80)
    print(f"N_START      = {format_int(start)}")
    print(f"N_END        = {format_int(end)}")
    print(f"SEGMENT_SIZE = {format_int(segment_size)}")
    print(f"PROGRESS     = every {progress_step}%")
    print(f"OVERWRITE    = {overwrite}")
    print(f"SKIP_EXISTING= {skip_existing}")
    print(f"REPOSITORY   = {REPOSITORY_ROOT}")
    print(f"RANGES_DIR   = {RANGES_DIR}")
    print("=" * 80)

    if out_file.exists():
        if skip_existing and not overwrite:
            print(f"[SKIP] Existing output found: {out_file}")
            return

        if overwrite:
            print(f"[OVERWRITE] Existing output will be replaced: {out_file}")
        else:
            raise FileExistsError(
                f"Output already exists: {out_file}\n"
                f"Use --overwrite or --skip-existing."
            )

    t0 = time.perf_counter()

    print("[START] Generating primes...")
    tg0 = time.perf_counter()
    primes = segmented_primes(start, end, segment_size, progress_step)
    tg1 = time.perf_counter()

    print("[SAVE] Writing NumPy file...")
    ts0 = time.perf_counter()
    np.save(out_file, primes)
    ts1 = time.perf_counter()

    print("[VERIFY] Reloading and verifying output...")
    tv0 = time.perf_counter()
    loaded = np.load(out_file, mmap_mode="r")
    verification = verify_prime_array(loaded, start, end)
    tv1 = time.perf_counter()

    if not verification["passed"]:
        raise RuntimeError(f"Verification failed for {out_file}")

    size_bytes = out_file.stat().st_size
    size_gb = size_bytes / (1024 ** 3)

    total_sec = time.perf_counter() - t0
    generate_sec = tg1 - tg0
    save_sec = ts1 - ts0
    verify_sec = tv1 - tv0

    status = "NORMAL"

    manifest_row = {
        "timestamp": now_string(),
        "start": start,
        "end": end,
        "filename": str(out_file),
        "count": verification["count"],
        "min_prime": verification["min_prime"],
        "max_prime": verification["max_prime"],
        "size_bytes": size_bytes,
        "size_gb": f"{size_gb:.6f}",
        "verify_passed": verification["passed"],
    }

    counts_row = {
        "timestamp": now_string(),
        "start": start,
        "end": end,
        "count": verification["count"],
        "min_prime": verification["min_prime"],
        "max_prime": verification["max_prime"],
    }

    runtime_row = {
        "timestamp": now_string(),
        "start": start,
        "end": end,
        "segment_size": segment_size,
        "count": verification["count"],
        "generate_sec": f"{generate_sec:.3f}",
        "save_sec": f"{save_sec:.3f}",
        "verify_sec": f"{verify_sec:.3f}",
        "total_sec": f"{total_sec:.3f}",
        "total_min": f"{total_sec / 60:.3f}",
        "size_bytes": size_bytes,
        "size_gb": f"{size_gb:.6f}",
        "status": status,
    }

    update_manifest(manifest_row)
    update_counts(counts_row)
    log_runtime(runtime_row)

    print("=" * 80)
    print("[SAVED]")
    print(f"File:   {out_file}")
    print(f"Count:  {format_int(verification['count'])}")
    print(f"Min:    {format_int(verification['min_prime'])}")
    print(f"Max:    {format_int(verification['max_prime'])}")
    print(f"Size:   {size_gb:.6f} GB")
    print()
    print("[RUNTIME]")
    print(f"Generate: {generate_sec:.3f} sec ({generate_sec / 60:.3f} min)")
    print(f"Save:     {save_sec:.3f} sec ({save_sec / 60:.3f} min)")
    print(f"Verify:   {verify_sec:.3f} sec")
    print(f"Total:    {total_sec:.3f} sec ({total_sec / 60:.3f} min)")
    print()
    print("Inventory updated.")
    print("Counts updated.")
    print("Verification passed.")
    print("=" * 80)


# =============================================================================
# CLI
# =============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PrimeNet Stage 1 official prime range builder."
    )

    parser.add_argument(
        "--start",
        type=int,
        required=True,
        help="Inclusive range start.",
    )

    parser.add_argument(
        "--end",
        type=int,
        required=True,
        help="Inclusive range end.",
    )

    parser.add_argument(
        "--segment-size",
        type=int,
        default=DEFAULT_SEGMENT_SIZE,
        help=f"Segment size. Default: {DEFAULT_SEGMENT_SIZE}",
    )

    parser.add_argument(
        "--progress-step",
        type=int,
        default=DEFAULT_PROGRESS_STEP,
        help=f"Progress print step in percent. Default: {DEFAULT_PROGRESS_STEP}",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output file.",
    )

    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip if output file already exists.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    build_range(
        start=args.start,
        end=args.end,
        segment_size=args.segment_size,
        progress_step=args.progress_step,
        overwrite=args.overwrite,
        skip_existing=args.skip_existing,
    )


if __name__ == "__main__":
    main()