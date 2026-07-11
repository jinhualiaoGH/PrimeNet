"""
PrimeNet Repository Builder
===========================

Build one prime range file for the PrimeNet repository.

Run from:

    C:\PrimeNet\Platform

Example:

    py -m core.build_prime_range --start 1 --end 1000000 --overwrite

The repository root, default segment size, and batch size are read from:

    Platform\config\repository.yaml
"""

from __future__ import annotations

import argparse
import csv
import math
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from core.configuration import config


GENERATOR_NAME = "PrimeNet Repository Builder"
GENERATOR_VERSION = "1.1.0"


REPOSITORY_DIR = config.repository_root
RANGES_DIR = REPOSITORY_DIR / "ranges"
METADATA_DIR = REPOSITORY_DIR / "metadata"
COUNTS_DIR = REPOSITORY_DIR / "counts"

INVENTORY_FILE = METADATA_DIR / "prime_inventory.csv"
COUNTS_FILE = COUNTS_DIR / "prime_counts.csv"


def runtime(label: str, start_time: float) -> float:
    sec = time.time() - start_time
    print(f"[RUNTIME] {label}: {sec:.3f} sec ({sec / 60:.3f} min)")
    return sec


def simple_sieve(limit: int) -> np.ndarray:
    if limit < 2:
        return np.array([], dtype=np.uint64)

    sieve = bytearray(b"\x01") * (limit + 1)
    sieve[0:2] = b"\x00\x00"

    for p in range(2, int(math.isqrt(limit)) + 1):
        if sieve[p]:
            start = p * p
            sieve[start : limit + 1 : p] = b"\x00" * (((limit - start) // p) + 1)

    return np.nonzero(np.frombuffer(sieve, dtype=np.uint8))[0].astype(np.uint64)


def should_print_progress(
    segment_id: int,
    total_segments: int,
    progress_step_percent: int,
    printed_percent_marks: set[int],
) -> bool:
    if segment_id == total_segments:
        printed_percent_marks.add(100)
        return True

    percent = int((segment_id * 100) / total_segments)
    mark = (percent // progress_step_percent) * progress_step_percent

    if mark > 0 and mark not in printed_percent_marks:
        printed_percent_marks.add(mark)
        return True

    return False


def segmented_primes(
    n_start: int,
    n_end: int,
    segment_size: int,
    progress_step_percent: int = 10,
) -> np.ndarray:
    base_primes = simple_sieve(math.isqrt(n_end) + 1)
    chunks: list[np.ndarray] = []

    low = max(2, n_start)

    if low > n_end:
        return np.array([], dtype=np.uint64)

    total_segments = ((n_end - low) // segment_size) + 1
    segment_id = 0
    total_primes_so_far = 0
    printed_percent_marks: set[int] = set()

    progress_step_percent = max(1, min(100, progress_step_percent))

    while low <= n_end:
        segment_id += 1
        high = min(low + segment_size - 1, n_end)

        mark = bytearray(b"\x01") * (high - low + 1)

        for p_raw in base_primes:
            p = int(p_raw)
            pp = p * p

            if pp > high:
                break

            first = max(pp, ((low + p - 1) // p) * p)
            mark[first - low : high - low + 1 : p] = b"\x00" * (
                ((high - first) // p) + 1
            )

        arr = np.nonzero(np.frombuffer(mark, dtype=np.uint8))[0] + low
        arr = arr.astype(np.uint64)

        chunks.append(arr)
        total_primes_so_far += len(arr)

        if should_print_progress(
            segment_id,
            total_segments,
            progress_step_percent,
            printed_percent_marks,
        ):
            percent = (segment_id / total_segments) * 100.0
            print(
                f"[PROGRESS] {percent:6.2f}% "
                f"({segment_id:,}/{total_segments:,} segments) "
                f"current={low:,}-{high:,} "
                f"primes_so_far={total_primes_so_far:,}"
            )

        low = high + 1

    if chunks:
        return np.concatenate(chunks)

    return np.array([], dtype=np.uint64)


def verify_prime_array(primes: np.ndarray, n_start: int, n_end: int) -> None:
    if primes.dtype != np.uint64:
        raise ValueError(f"Invalid dtype: {primes.dtype}")

    if len(primes) == 0:
        return

    if int(primes[0]) < max(2, n_start):
        raise ValueError("First prime is below requested range.")

    if int(primes[-1]) > n_end:
        raise ValueError("Last prime exceeds requested range.")

    if len(primes) > 1:
        if not np.all(np.diff(primes) > 0):
            raise ValueError("Prime array is not strictly increasing.")


def append_csv(path: Path, row: dict, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not exists:
            writer.writeheader()

        writer.writerow(row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build one PrimeNet prime repository range."
    )

    parser.add_argument(
        "--start",
        type=int,
        required=True,
        help="Inclusive start of integer range.",
    )

    parser.add_argument(
        "--end",
        type=int,
        required=True,
        help="Inclusive end of integer range.",
    )

    parser.add_argument(
        "--segment-size",
        type=int,
        default=config.segment_size,
        help="Segment size. Default comes from repository.yaml.",
    )

    parser.add_argument(
        "--progress-step-percent",
        type=int,
        default=config.progress_step_percent,
        help="Console progress interval in percent. Default comes from repository.yaml.",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing .npy output file for this range.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    n_start = args.start
    n_end = args.end
    segment_size = args.segment_size
    progress_step_percent = args.progress_step_percent

    if n_start < 1:
        raise ValueError("--start must be >= 1")

    if n_end < n_start:
        raise ValueError("--end must be >= --start")

    if segment_size < 1:
        raise ValueError("--segment-size must be >= 1")

    RANGES_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    COUNTS_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"primes_{n_start}_{n_end}.npy"
    out_file = RANGES_DIR / filename

    if out_file.exists():
        if args.overwrite:
            print(f"[OVERWRITE] Existing output will be replaced: {out_file}")
            out_file.unlink()
        else:
            raise FileExistsError(
                f"Output file already exists: {out_file}. "
                f"Use --overwrite or set driver.overwrite_existing: true."
            )

    print("=" * 80)
    print(f"{GENERATOR_NAME} v{GENERATOR_VERSION}")
    print("=" * 80)
    print(f"N_START      = {n_start:,}")
    print(f"N_END        = {n_end:,}")
    print(f"BATCH_SIZE   = {config.batch_size:,}")
    print(f"SEGMENT_SIZE = {segment_size:,}")
    print(f"PROGRESS     = every {progress_step_percent}%")
    print(f"OVERWRITE    = {args.overwrite}")
    print(f"REPOSITORY   = {config.repository_root}")
    print(f"RANGES_DIR   = {RANGES_DIR}")
    print("=" * 80)

    t_generate = time.time()
    primes = segmented_primes(
        n_start,
        n_end,
        segment_size,
        progress_step_percent=progress_step_percent,
    )
    generate_sec = runtime("generate_primes", t_generate)

    t_verify = time.time()
    verify_prime_array(primes, n_start, n_end)
    verify_sec = runtime("verify_prime_array", t_verify)

    t_save = time.time()
    np.save(out_file, primes)
    save_sec = runtime("save_npy", t_save)

    if not out_file.exists():
        raise RuntimeError("Output file was not created.")

    file_size_bytes = out_file.stat().st_size
    file_size_gb = file_size_bytes / (1024**3)

    prime_count = len(primes)
    min_prime = int(primes[0]) if prime_count else None
    max_prime = int(primes[-1]) if prime_count else None

    total_sec = generate_sec + verify_sec + save_sec
    total_min = total_sec / 60.0

    timestamp = datetime.now().isoformat(timespec="seconds")

    inventory_row = {
        "file_name": filename,
        "n_start": n_start,
        "n_end": n_end,
        "prime_count": prime_count,
        "min_prime": min_prime,
        "max_prime": max_prime,
        "dtype": str(primes.dtype),
        "file_size_bytes": file_size_bytes,
        "file_size_gb": f"{file_size_gb:.6f}",
        "runtime_seconds": f"{total_sec:.3f}",
        "runtime_minutes": f"{total_min:.6f}",
        "generate_seconds": f"{generate_sec:.3f}",
        "verify_seconds": f"{verify_sec:.3f}",
        "save_seconds": f"{save_sec:.3f}",
        "generated_at": timestamp,
        "generator_name": GENERATOR_NAME,
        "generator_version": GENERATOR_VERSION,
        "python_version": sys.version.split()[0],
        "numpy_version": np.__version__,
        "machine": platform.node(),
        "system": platform.system(),
        "batch_size": config.batch_size,
        "segment_size": segment_size,
        "progress_step_percent": progress_step_percent,
        "overwrite": args.overwrite,
        "repository_root": str(config.repository_root),
    }

    inventory_fields = [
        "file_name",
        "n_start",
        "n_end",
        "prime_count",
        "min_prime",
        "max_prime",
        "dtype",
        "file_size_bytes",
        "file_size_gb",
        "runtime_seconds",
        "runtime_minutes",
        "generate_seconds",
        "verify_seconds",
        "save_seconds",
        "generated_at",
        "generator_name",
        "generator_version",
        "python_version",
        "numpy_version",
        "machine",
        "system",
        "batch_size",
        "segment_size",
        "progress_step_percent",
        "overwrite",
        "repository_root",
    ]

    append_csv(INVENTORY_FILE, inventory_row, inventory_fields)

    append_csv(
        COUNTS_FILE,
        {
            "n_start": n_start,
            "n_end": n_end,
            "prime_count": prime_count,
        },
        ["n_start", "n_end", "prime_count"],
    )

    print("=" * 80)
    print("[DONE] Range generated successfully.")
    print(f"Saved:       {out_file}")
    print(f"File size:   {file_size_gb:.6f} GB")
    print(f"Prime count: {prime_count:,}")
    print(f"Min prime:   {min_prime}")
    print(f"Max prime:   {max_prime}")
    print(f"Generate:    {generate_sec:.3f} sec ({generate_sec / 60:.3f} min)")
    print(f"Verify:      {verify_sec:.3f} sec")
    print(f"Save:        {save_sec:.3f} sec ({save_sec / 60:.3f} min)")
    print(f"Total:       {total_sec:.3f} sec ({total_min:.3f} min)")
    print("Inventory updated.")
    print("Counts updated.")
    print("Verification passed.")
    print("=" * 80)


if __name__ == "__main__":
    main()
