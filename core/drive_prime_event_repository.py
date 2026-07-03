"""
PrimeNet Prime Event Repository Driver v1.1.0

Builds compact prime-event files for all repository ranges.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

VERSION = "1.1.0"

REPOSITORY_ROOT = Path(r"E:\PrimeNet\Repository")
PRIME_EVENTS_DIR = REPOSITORY_ROOT / "prime_events"
LOGS_DIR = REPOSITORY_ROOT / "logs"
RUNTIME_LOG = LOGS_DIR / "prime_event_builder_runtime.csv"

DEFAULT_START = 1
DEFAULT_END = 1_000_000_000_000
DEFAULT_BATCH_SIZE = 10_000_000_000


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def iter_ranges(start: int, end: int, batch_size: int):
    current = start
    while current <= end:
        batch_end = min(current + batch_size - 1, end)
        yield current, batch_end
        current = batch_end + 1


def ensure_runtime_log() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    if not RUNTIME_LOG.exists():
        with RUNTIME_LOG.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "run_utc",
                "batch_index",
                "total_batches",
                "range_start",
                "range_end",
                "status",
                "runtime_seconds",
                "runtime_minutes",
            ])


def append_runtime(row: list) -> None:
    with RUNTIME_LOG.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the full compact PrimeNet prime-event repository.")
    parser.add_argument("--start", type=int, default=DEFAULT_START)
    parser.add_argument("--end", type=int, default=DEFAULT_END)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()

    ranges = list(iter_ranges(args.start, args.end, args.batch_size))
    total_batches = len(ranges)

    PRIME_EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    ensure_runtime_log()

    print("=" * 80)
    print(f"PrimeNet Prime Event Repository Driver v{VERSION}")
    print("=" * 80)
    print(f"Repository root = {REPOSITORY_ROOT}")
    print(f"Range start     = {args.start:,}")
    print(f"Range end       = {args.end:,}")
    print(f"Batch size      = {args.batch_size:,}")
    print(f"Total batches   = {total_batches}")
    print(f"Overwrite       = {args.overwrite}")
    print(f"Skip existing   = {args.skip_existing}")
    print(f"Runtime log     = {RUNTIME_LOG}")
    print("=" * 80)

    passed = 0
    failed = 0
    skipped = 0
    run_t0 = time.perf_counter()

    for i, (start, end) in enumerate(ranges, start=1):
        output_file = PRIME_EVENTS_DIR / f"prime_events_{start}_{end}.npy"

        print()
        print("-" * 80)
        print(f"[BATCH {i}/{total_batches}] {start:,} - {end:,}")
        print(f"Output: {output_file}")

        if output_file.exists() and args.skip_existing and not args.overwrite:
            print("[SKIPPED] output exists")
            skipped += 1
            append_runtime([utc_now(), i, total_batches, start, end, "SKIPPED", 0.0, 0.0])
            continue

        cmd = [
            sys.executable,
            "-m",
            "core.build_prime_events",
            "--start",
            str(start),
            "--end",
            str(end),
        ]
        if args.overwrite:
            cmd.append("--overwrite")

        t0 = time.perf_counter()
        status = "FAILED"
        try:
            subprocess.run(cmd, check=True)
            status = "PASSED"
            passed += 1
        except subprocess.CalledProcessError as exc:
            failed += 1
            print(f"[FAILED] return code: {exc.returncode}")
        runtime_seconds = time.perf_counter() - t0

        append_runtime([
            utc_now(),
            i,
            total_batches,
            start,
            end,
            status,
            f"{runtime_seconds:.6f}",
            f"{runtime_seconds / 60:.6f}",
        ])

        if status == "FAILED":
            break

    total_runtime = time.perf_counter() - run_t0

    print()
    print("=" * 80)
    print("Prime Event Repository Driver Complete")
    print(f"Passed   = {passed}")
    print(f"Failed   = {failed}")
    print(f"Skipped  = {skipped}")
    print(f"Runtime  = {total_runtime:.3f} sec ({total_runtime / 60:.3f} min)")
    print("=" * 80)


if __name__ == "__main__":
    main()
