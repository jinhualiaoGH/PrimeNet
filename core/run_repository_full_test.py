"""
PrimeNet Repository Full 1T Test

Purpose:
    Streaming read-only end-to-end test of the verified PrimeNet repository.

Checks:
    - Finds all .npy range files
    - Loads each file safely with mmap_mode="r"
    - Verifies each array is sorted
    - Verifies no duplicate primes inside each block
    - Verifies block boundaries are strictly increasing
    - Counts total primes
    - Counts total prime gaps/events
    - Tracks min/max prime
    - Tracks min/max gap
    - Writes summary report

Run:
    py -m core.run_repository_full_test

Recommended overnight run:
    py -m core.run_repository_full_test *> E:\\PrimeNet\\Repository\\metadata\\full_1T_test_console_log.txt
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


REPOSITORY_ROOT = Path(r"E:\PrimeNet\Repository")
RANGES_DIR = REPOSITORY_ROOT / "ranges"
METADATA_DIR = REPOSITORY_ROOT / "metadata"

SUMMARY_TXT = METADATA_DIR / "full_1T_test_summary.txt"
SUMMARY_JSON = METADATA_DIR / "full_1T_test_summary.json"
GAP_HIST_CSV = METADATA_DIR / "full_1T_gap_histogram.csv"


@dataclass
class BlockResult:
    file: str
    count: int
    min_prime: int
    max_prime: int
    min_gap: Optional[int]
    max_gap: Optional[int]
    first_gap_from_previous: Optional[int]
    passed: bool
    error: str = ""


def parse_range_from_name(path: Path) -> tuple[int, int]:
    """
    Expected filename format:
        primes_START_END.npy
    """
    stem = path.stem
    parts = stem.split("_")
    if len(parts) < 3 or parts[0] != "primes":
        raise ValueError(f"Invalid range filename: {path.name}")
    return int(parts[1]), int(parts[2])


def find_range_files() -> list[Path]:
    files = sorted(RANGES_DIR.glob("primes_*.npy"), key=parse_range_from_name)
    return files


def fmt_int(n: Optional[int]) -> str:
    if n is None:
        return "None"
    return f"{n:,}"


def update_gap_histogram(hist: dict[int, int], gaps: np.ndarray) -> None:
    if gaps.size == 0:
        return
    values, counts = np.unique(gaps, return_counts=True)
    for g, c in zip(values, counts):
        hist[int(g)] = hist.get(int(g), 0) + int(c)


def write_gap_histogram(hist: dict[int, int]) -> None:
    with GAP_HIST_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["gap", "count"])
        for gap in sorted(hist):
            writer.writerow([gap, hist[gap]])


def main() -> None:
    t0 = time.time()
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("PrimeNet Repository Full 1T Test")
    print("=" * 80)
    print(f"Repository root = {REPOSITORY_ROOT}")
    print(f"Ranges dir      = {RANGES_DIR}")
    print(f"Summary TXT     = {SUMMARY_TXT}")
    print(f"Summary JSON    = {SUMMARY_JSON}")
    print(f"Gap histogram   = {GAP_HIST_CSV}")
    print("=" * 80)

    files = find_range_files()
    expected_blocks = 100

    print(f"Found range files: {len(files)}")
    print()

    if not files:
        raise RuntimeError(f"No range files found in {RANGES_DIR}")

    results: list[BlockResult] = []
    gap_hist: dict[int, int] = {}

    total_primes = 0
    total_gaps = 0

    global_min_prime: Optional[int] = None
    global_max_prime: Optional[int] = None
    global_min_gap: Optional[int] = None
    global_max_gap: Optional[int] = None

    previous_last_prime: Optional[int] = None
    failed = 0

    for i, path in enumerate(files, start=1):
        block_t0 = time.time()
        print("-" * 80)
        print(f"[{i}/{len(files)}] {path.name}")

        try:
            arr = np.load(path, mmap_mode="r")

            if arr.ndim != 1:
                raise ValueError(f"Array is not 1D: ndim={arr.ndim}")

            count = int(arr.shape[0])
            if count == 0:
                raise ValueError("Array is empty")

            min_prime = int(arr[0])
            max_prime = int(arr[-1])

            if global_min_prime is None:
                global_min_prime = min_prime
            global_max_prime = max_prime

            if previous_last_prime is not None and min_prime <= previous_last_prime:
                raise ValueError(
                    f"Block boundary not strictly increasing: "
                    f"previous_last={previous_last_prime}, current_first={min_prime}"
                )

            first_gap_from_previous: Optional[int] = None
            if previous_last_prime is not None:
                first_gap_from_previous = min_prime - previous_last_prime
                if first_gap_from_previous <= 0:
                    raise ValueError(
                        f"Invalid boundary gap: {first_gap_from_previous}"
                    )

                gap_hist[first_gap_from_previous] = (
                    gap_hist.get(first_gap_from_previous, 0) + 1
                )

                total_gaps += 1

                if global_min_gap is None or first_gap_from_previous < global_min_gap:
                    global_min_gap = first_gap_from_previous
                if global_max_gap is None or first_gap_from_previous > global_max_gap:
                    global_max_gap = first_gap_from_previous

            gaps = np.diff(arr)

            if gaps.size > 0:
                local_min_gap = int(gaps.min())
                local_max_gap = int(gaps.max())

                if local_min_gap <= 0:
                    raise ValueError(f"Array not strictly increasing; min_gap={local_min_gap}")

                update_gap_histogram(gap_hist, gaps)

                total_gaps += int(gaps.size)

                if global_min_gap is None or local_min_gap < global_min_gap:
                    global_min_gap = local_min_gap
                if global_max_gap is None or local_max_gap > global_max_gap:
                    global_max_gap = local_max_gap
            else:
                local_min_gap = None
                local_max_gap = None

            total_primes += count
            previous_last_prime = max_prime

            elapsed = time.time() - block_t0

            print(
                f"[PASSED] count={count:,}, "
                f"min={min_prime:,}, max={max_prime:,}, "
                f"local_min_gap={fmt_int(local_min_gap)}, "
                f"local_max_gap={fmt_int(local_max_gap)}, "
                f"boundary_gap={fmt_int(first_gap_from_previous)}, "
                f"runtime={elapsed:.3f} sec"
            )

            results.append(
                BlockResult(
                    file=path.name,
                    count=count,
                    min_prime=min_prime,
                    max_prime=max_prime,
                    min_gap=local_min_gap,
                    max_gap=local_max_gap,
                    first_gap_from_previous=first_gap_from_previous,
                    passed=True,
                )
            )

        except Exception as e:
            failed += 1
            elapsed = time.time() - block_t0
            print(f"[FAILED] {path.name}")
            print(f"Error: {e}")
            print(f"runtime={elapsed:.3f} sec")

            results.append(
                BlockResult(
                    file=path.name,
                    count=0,
                    min_prime=0,
                    max_prime=0,
                    min_gap=None,
                    max_gap=None,
                    first_gap_from_previous=None,
                    passed=False,
                    error=str(e),
                )
            )

    passed = len(files) - failed
    total_elapsed = time.time() - t0

    status = "PASSED" if failed == 0 and len(files) == expected_blocks else "FAILED"

    write_gap_histogram(gap_hist)

    summary = {
        "test_name": "PrimeNet Repository Full 1T Test",
        "status": status,
        "repository_root": str(REPOSITORY_ROOT),
        "ranges_dir": str(RANGES_DIR),
        "expected_blocks": expected_blocks,
        "found_blocks": len(files),
        "passed_blocks": passed,
        "failed_blocks": failed,
        "total_primes": total_primes,
        "total_gaps": total_gaps,
        "global_min_prime": global_min_prime,
        "global_max_prime": global_max_prime,
        "global_min_gap": global_min_gap,
        "global_max_gap": global_max_gap,
        "unique_gap_count": len(gap_hist),
        "runtime_seconds": total_elapsed,
        "runtime_minutes": total_elapsed / 60.0,
        "summary_txt": str(SUMMARY_TXT),
        "summary_json": str(SUMMARY_JSON),
        "gap_histogram_csv": str(GAP_HIST_CSV),
        "blocks": [r.__dict__ for r in results],
    }

    with SUMMARY_JSON.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    with SUMMARY_TXT.open("w", encoding="utf-8") as f:
        f.write("PrimeNet Repository Full 1T Test\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Status:              {status}\n")
        f.write(f"Repository root:     {REPOSITORY_ROOT}\n")
        f.write(f"Ranges dir:          {RANGES_DIR}\n")
        f.write(f"Expected blocks:     {expected_blocks}\n")
        f.write(f"Found blocks:        {len(files)}\n")
        f.write(f"Passed blocks:       {passed}\n")
        f.write(f"Failed blocks:       {failed}\n")
        f.write(f"Total primes:        {total_primes:,}\n")
        f.write(f"Total gaps/events:   {total_gaps:,}\n")
        f.write(f"Global min prime:    {fmt_int(global_min_prime)}\n")
        f.write(f"Global max prime:    {fmt_int(global_max_prime)}\n")
        f.write(f"Global min gap:      {fmt_int(global_min_gap)}\n")
        f.write(f"Global max gap:      {fmt_int(global_max_gap)}\n")
        f.write(f"Unique gap count:    {len(gap_hist):,}\n")
        f.write(f"Runtime seconds:     {total_elapsed:.3f}\n")
        f.write(f"Runtime minutes:     {total_elapsed / 60.0:.3f}\n")
        f.write(f"Gap histogram CSV:   {GAP_HIST_CSV}\n")
        f.write("\n")
        f.write("Block Results\n")
        f.write("-" * 80 + "\n")

        for r in results:
            f.write(
                f"{r.file}: "
                f"{'PASSED' if r.passed else 'FAILED'}, "
                f"count={r.count:,}, "
                f"min={fmt_int(r.min_prime)}, "
                f"max={fmt_int(r.max_prime)}, "
                f"min_gap={fmt_int(r.min_gap)}, "
                f"max_gap={fmt_int(r.max_gap)}, "
                f"boundary_gap={fmt_int(r.first_gap_from_previous)}"
            )
            if r.error:
                f.write(f", error={r.error}")
            f.write("\n")

    print()
    print("=" * 80)
    print("Full 1T repository test complete.")
    print(f"Status:        {status}")
    print(f"Expected:      {expected_blocks}")
    print(f"Found:         {len(files)}")
    print(f"Passed:        {passed}")
    print(f"Failed:        {failed}")
    print(f"Total primes:  {total_primes:,}")
    print(f"Total gaps:    {total_gaps:,}")
    print(f"Min prime:     {fmt_int(global_min_prime)}")
    print(f"Max prime:     {fmt_int(global_max_prime)}")
    print(f"Min gap:       {fmt_int(global_min_gap)}")
    print(f"Max gap:       {fmt_int(global_max_gap)}")
    print(f"Unique gaps:   {len(gap_hist):,}")
    print(f"Runtime:       {total_elapsed / 60.0:.3f} min")
    print(f"Summary TXT:   {SUMMARY_TXT}")
    print(f"Summary JSON:  {SUMMARY_JSON}")
    print(f"Gap CSV:       {GAP_HIST_CSV}")
    print("=" * 80)


if __name__ == "__main__":
    main()