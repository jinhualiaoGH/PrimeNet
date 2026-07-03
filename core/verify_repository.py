"""
PrimeNet Repository Verifier
============================

Verify PrimeNet prime repository files and produce a manifest.

Run from:

    C:\\PrimeNet\\Platform

Command:

    py -m core.verify_repository
"""

from __future__ import annotations

import csv
import hashlib
import re
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from core.configuration import config


VERIFIER_NAME = "PrimeNet Repository Verifier"
VERIFIER_VERSION = "1.0.0"

REPOSITORY_DIR = config.repository_root
RANGES_DIR = REPOSITORY_DIR / "ranges"
METADATA_DIR = REPOSITORY_DIR / "metadata"

MANIFEST_FILE = METADATA_DIR / "repository_manifest.csv"
SUMMARY_FILE = METADATA_DIR / "repository_verification_summary.txt"

FILENAME_RE = re.compile(r"^primes_(\d+)_(\d+)\.npy$")


def sha256_file(path: Path, block_size: int = 1024 * 1024 * 16) -> str:
    h = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            block = f.read(block_size)
            if not block:
                break
            h.update(block)

    return h.hexdigest()


def parse_range_from_filename(path: Path) -> tuple[int, int]:
    m = FILENAME_RE.match(path.name)

    if not m:
        raise ValueError(f"Invalid filename format: {path.name}")

    return int(m.group(1)), int(m.group(2))


def verify_array(path: Path, expected_start: int, expected_end: int) -> dict:
    arr = np.load(path, mmap_mode="r")

    status = "passed"
    messages: list[str] = []

    if arr.dtype != np.uint64:
        status = "failed"
        messages.append(f"invalid_dtype={arr.dtype}")

    prime_count = int(len(arr))

    if prime_count > 0:
        min_prime = int(arr[0])
        max_prime = int(arr[-1])

        if min_prime < max(2, expected_start):
            status = "failed"
            messages.append("min_prime_below_range")

        if max_prime > expected_end:
            status = "failed"
            messages.append("max_prime_above_range")

        diffs = np.diff(arr)

        if len(diffs) > 0 and not np.all(diffs > 0):
            status = "failed"
            messages.append("not_strictly_increasing")

    else:
        min_prime = None
        max_prime = None

    return {
        "status": status,
        "messages": ";".join(messages),
        "prime_count": prime_count,
        "min_prime": min_prime,
        "max_prime": max_prime,
        "dtype": str(arr.dtype),
    }


def expected_ranges() -> list[tuple[int, int]]:
    ranges = []

    current = config.repository_start
    end_limit = config.repository_end
    batch_size = config.batch_size

    while current <= end_limit:
        end = min(current + batch_size - 1, end_limit)
        ranges.append((current, end))
        current = end + 1

    return ranges


def write_manifest(rows: list[dict]) -> None:
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    fields = [
        "file_name",
        "n_start",
        "n_end",
        "file_size_gb",
        "prime_count",
        "min_prime",
        "max_prime",
        "dtype",
        "sha256",
        "status",
        "messages",
        "verified_at",
        "verifier_version",
    ]

    with open(MANIFEST_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(
    total_expected: int,
    total_found: int,
    total_passed: int,
    total_failed: int,
    total_missing: int,
    runtime_sec: float,
) -> None:
    text = f"""
PrimeNet Repository Verification Summary
=======================================

Verified at: {datetime.now().isoformat(timespec="seconds")}
Verifier version: {VERIFIER_VERSION}

Repository root: {REPOSITORY_DIR}
Ranges directory: {RANGES_DIR}

Configured start: {config.repository_start}
Configured end: {config.repository_end}
Batch size: {config.batch_size}
Segment size: {config.segment_size}

Expected files: {total_expected}
Found files: {total_found}
Passed files: {total_passed}
Failed files: {total_failed}
Missing files: {total_missing}

Runtime seconds: {runtime_sec:.3f}
Runtime minutes: {runtime_sec / 60.0:.6f}

Manifest:
{MANIFEST_FILE}
"""

    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write(text.strip() + "\n")


def main() -> None:
    t0 = time.time()

    print("=" * 80)
    print(f"{VERIFIER_NAME} v{VERIFIER_VERSION}")
    print("=" * 80)
    print(f"Repository root = {REPOSITORY_DIR}")
    print(f"Ranges dir      = {RANGES_DIR}")
    print(f"Manifest        = {MANIFEST_FILE}")
    print("=" * 80)

    expected = expected_ranges()
    rows: list[dict] = []

    total_passed = 0
    total_failed = 0
    total_missing = 0

    for idx, (start, end) in enumerate(expected, start=1):
        path = RANGES_DIR / f"primes_{start}_{end}.npy"

        print()
        print("-" * 80)
        print(f"[{idx}/{len(expected)}] {start:,} - {end:,}")

        if not path.exists():
            print("[MISSING]")
            total_missing += 1

            rows.append(
                {
                    "file_name": path.name,
                    "n_start": start,
                    "n_end": end,
                    "file_size_gb": "0.000000",
                    "prime_count": "",
                    "min_prime": "",
                    "max_prime": "",
                    "dtype": "",
                    "sha256": "",
                    "status": "missing",
                    "messages": "file_missing",
                    "verified_at": datetime.now().isoformat(timespec="seconds"),
                    "verifier_version": VERIFIER_VERSION,
                }
            )

            continue

        file_size_gb = path.stat().st_size / (1024**3)

        try:
            file_start, file_end = parse_range_from_filename(path)

            if file_start != start or file_end != end:
                raise ValueError("filename_range_mismatch")

            result = verify_array(path, start, end)
            checksum = sha256_file(path)

            status = result["status"]

            if status == "passed":
                total_passed += 1
            else:
                total_failed += 1

            print(
                f"[{status.upper()}] "
                f"count={result['prime_count']:,}, "
                f"min={result['min_prime']}, "
                f"max={result['max_prime']}, "
                f"size={file_size_gb:.6f} GB"
            )

            rows.append(
                {
                    "file_name": path.name,
                    "n_start": start,
                    "n_end": end,
                    "file_size_gb": f"{file_size_gb:.6f}",
                    "prime_count": result["prime_count"],
                    "min_prime": result["min_prime"],
                    "max_prime": result["max_prime"],
                    "dtype": result["dtype"],
                    "sha256": checksum,
                    "status": status,
                    "messages": result["messages"],
                    "verified_at": datetime.now().isoformat(timespec="seconds"),
                    "verifier_version": VERIFIER_VERSION,
                }
            )

        except Exception as exc:
            total_failed += 1
            print(f"[FAILED] {exc}")

            rows.append(
                {
                    "file_name": path.name,
                    "n_start": start,
                    "n_end": end,
                    "file_size_gb": f"{file_size_gb:.6f}",
                    "prime_count": "",
                    "min_prime": "",
                    "max_prime": "",
                    "dtype": "",
                    "sha256": "",
                    "status": "failed",
                    "messages": str(exc),
                    "verified_at": datetime.now().isoformat(timespec="seconds"),
                    "verifier_version": VERIFIER_VERSION,
                }
            )

    runtime_sec = time.time() - t0

    total_expected = len(expected)
    total_found = total_expected - total_missing

    write_manifest(rows)
    write_summary(
        total_expected=total_expected,
        total_found=total_found,
        total_passed=total_passed,
        total_failed=total_failed,
        total_missing=total_missing,
        runtime_sec=runtime_sec,
    )

    print()
    print("=" * 80)
    print("Verification complete.")
    print(f"Expected: {total_expected}")
    print(f"Found:    {total_found}")
    print(f"Passed:   {total_passed}")
    print(f"Failed:   {total_failed}")
    print(f"Missing:  {total_missing}")
    print(f"Manifest: {MANIFEST_FILE}")
    print(f"Summary:  {SUMMARY_FILE}")
    print("=" * 80)


if __name__ == "__main__":
    main()