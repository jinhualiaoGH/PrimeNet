"""
PrimeNet Repository Verifier
============================

Verify PrimeNet prime repository files and produce verification artifacts.

Modes
-----
fast:
    Operational readiness verification. Checks repository topology,
    file loadability, shape, dtype, non-empty arrays, endpoint range
    consistency, and cross-file prime ordering. Skips full-array
    monotonic scanning and SHA-256 hashing.

full:
    Formal repository certification. Performs all fast checks plus
    complete per-file monotonic scanning and SHA-256 hashing.

Run from:

    C:\\PrimeNet\\Platform

Commands:

    py -m core.verify_repository --mode fast
    py -m core.verify_repository --mode full
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from core.platform_config import load_platform_config
from core.range_files import sorted_range_files, validate_adjacency


VERIFIER_NAME = "PrimeNet Repository Verifier"
VERIFIER_VERSION = "1.2.1"

CONFIG = load_platform_config()
PATHS = CONFIG.paths
CAMPAIGN = CONFIG.campaign

REPOSITORY_DIR = PATHS.repository_root
RANGES_DIR = PATHS.ranges_dir
METADATA_DIR = PATHS.metadata_dir

CAMPAIGN_START = CAMPAIGN.start
CAMPAIGN_END = CAMPAIGN.end
BATCH_SIZE = CAMPAIGN.range_size
SEGMENT_SIZE = CAMPAIGN.segment_size

FULL_MANIFEST_FILE = METADATA_DIR / "repository_manifest.csv"
FULL_SUMMARY_FILE = METADATA_DIR / "repository_verification_summary.txt"
FAST_MANIFEST_FILE = METADATA_DIR / "repository_fast_manifest.csv"
FAST_SUMMARY_FILE = METADATA_DIR / "repository_fast_verification_summary.txt"

FILENAME_RE = re.compile(r"^primes_(\d+)_(\d+)\.npy$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the PrimeNet prime repository."
    )
    parser.add_argument(
        "--mode",
        choices=("fast", "full"),
        default="full",
        help=(
            "Verification mode. 'fast' skips full-array monotonic scans "
            "and SHA-256 hashing. Default: full."
        ),
    )
    return parser.parse_args()


def verification_artifacts(mode: str) -> tuple[Path, Path]:
    if mode == "fast":
        return FAST_MANIFEST_FILE, FAST_SUMMARY_FILE
    return FULL_MANIFEST_FILE, FULL_SUMMARY_FILE


def sha256_file(
    path: Path,
    block_size: int = 1024 * 1024 * 16,
) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(block_size)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def parse_range_from_filename(path: Path) -> tuple[int, int]:
    match = FILENAME_RE.match(path.name)
    if not match:
        raise ValueError(f"Invalid filename format: {path.name}")
    return int(match.group(1)), int(match.group(2))


def verify_array(
    path: Path,
    expected_start: int,
    expected_end: int,
    *,
    full_scan: bool,
) -> dict:
    arr = np.load(path, mmap_mode="r")

    status = "passed"
    messages: list[str] = []

    if arr.ndim != 1:
        status = "failed"
        messages.append(f"invalid_shape={arr.shape}")
        return {
            "status": status,
            "messages": ";".join(messages),
            "prime_count": int(arr.size),
            "min_prime": None,
            "max_prime": None,
            "dtype": str(arr.dtype),
        }

    if arr.dtype != np.uint64:
        status = "failed"
        messages.append(f"invalid_dtype={arr.dtype}")

    prime_count = int(arr.size)

    if prime_count == 0:
        status = "failed"
        messages.append("empty_array")
        min_prime = None
        max_prime = None
    else:
        min_prime = int(arr[0])
        max_prime = int(arr[-1])

        if min_prime < max(2, expected_start):
            status = "failed"
            messages.append("min_prime_below_range")

        if max_prime > expected_end:
            status = "failed"
            messages.append("max_prime_above_range")

        if (
            full_scan
            and prime_count > 1
            and not np.all(arr[1:] > arr[:-1])
        ):
            status = "failed"
            messages.append("not_strictly_increasing")

    return {
        "status": status,
        "messages": ";".join(messages),
        "prime_count": prime_count,
        "min_prime": min_prime,
        "max_prime": max_prime,
        "dtype": str(arr.dtype),
    }


def expected_ranges() -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    current = CAMPAIGN_START
    end_limit = CAMPAIGN_END
    batch_size = BATCH_SIZE

    while current <= end_limit:
        end = min(current + batch_size - 1, end_limit)
        ranges.append((current, end))
        current = end + 1

    return ranges


def write_manifest(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "verification_mode",
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

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(
    path: Path,
    *,
    verification_mode: str,
    total_expected: int,
    total_discovered: int,
    total_found: int,
    total_passed: int,
    total_failed: int,
    total_missing: int,
    total_topology_errors: int,
    accepted: bool,
    runtime_sec: float,
    manifest_file: Path,
) -> None:
    full_scan = verification_mode == "full"

    text = f"""
PrimeNet Repository Verification Summary
=======================================

Verified at: {datetime.now().isoformat(timespec="seconds")}
Verifier version: {VERIFIER_VERSION}
Verification mode: {verification_mode}

Repository root: {REPOSITORY_DIR}
Ranges directory: {RANGES_DIR}

Configured start: {CAMPAIGN_START}
Configured end: {CAMPAIGN_END}
Batch size: {BATCH_SIZE}
Segment size: {SEGMENT_SIZE}

Expected files: {total_expected}
Discovered files: {total_discovered}
Found files: {total_found}
Passed files: {total_passed}
Failed files: {total_failed}
Missing files: {total_missing}
Topology errors: {total_topology_errors}
Accepted: {accepted}

Full-array monotonic scan: {full_scan}
SHA-256 hashing: {full_scan}

Runtime seconds: {runtime_sec:.3f}
Runtime minutes: {runtime_sec / 60.0:.6f}

Manifest:
{manifest_file}
"""

    with path.open("w", encoding="utf-8") as f:
        f.write(text.strip() + "\n")


def verify_cross_file_boundaries(range_files) -> list[str]:
    """
    Verify strict prime ordering across adjacent repository files.

    For each neighboring pair:
        last_prime(file_k) < first_prime(file_k+1)
    """
    issues: list[str] = []

    for index in range(len(range_files) - 1):
        current = range_files[index]
        following = range_files[index + 1]

        current_arr = np.load(current.path, mmap_mode="r")
        following_arr = np.load(following.path, mmap_mode="r")

        if current_arr.ndim != 1 or following_arr.ndim != 1:
            issues.append(
                "boundary_shape_error: "
                f"{current.path.name} shape={current_arr.shape}, "
                f"{following.path.name} shape={following_arr.shape}"
            )
            continue

        if current_arr.size == 0 or following_arr.size == 0:
            issues.append(
                "boundary_empty_array: "
                f"{current.path.name} size={current_arr.size}, "
                f"{following.path.name} size={following_arr.size}"
            )
            continue

        current_last = int(current_arr[-1])
        following_first = int(following_arr[0])

        if current_last >= following_first:
            issues.append(
                "boundary_order_error: "
                f"{current.path.name} last={current_last}, "
                f"{following.path.name} first={following_first}"
            )

    return issues


def main() -> None:
    args = parse_args()
    mode = args.mode
    full_scan = mode == "full"
    manifest_file, summary_file = verification_artifacts(mode)

    t0 = time.time()

    print("=" * 80)
    print(f"{VERIFIER_NAME} v{VERIFIER_VERSION}")
    print("=" * 80)
    print(f"Verification mode = {mode}")
    print(f"Repository root   = {REPOSITORY_DIR}")
    print(f"Ranges dir        = {RANGES_DIR}")
    print(f"Manifest          = {manifest_file}")
    print(f"Summary           = {summary_file}")
    print(f"Full array scan   = {full_scan}")
    print(f"SHA-256 hashing   = {full_scan}")
    print("=" * 80)

    expected = expected_ranges()
    rows: list[dict] = []

    all_discovered_ranges = sorted_range_files(RANGES_DIR, "primes")

    discovered_ranges = [
        range_file
        for range_file in all_discovered_ranges
        if (
            range_file.start >= CAMPAIGN_START
            and range_file.end <= CAMPAIGN_END
        )
    ]

    adjacency_issues = validate_adjacency(discovered_ranges)
    boundary_issues = verify_cross_file_boundaries(discovered_ranges)

    expected_keys = set(expected)
    discovered_keys = {
        (range_file.start, range_file.end)
        for range_file in discovered_ranges
    }

    missing_ranges = sorted(expected_keys - discovered_keys)
    extra_ranges = sorted(discovered_keys - expected_keys)

    total_topology_errors = (
        len(adjacency_issues)
        + len(boundary_issues)
        + len(missing_ranges)
        + len(extra_ranges)
    )

    print()
    print("Repository topology")
    print("-" * 80)
    print(f"Physical ranges      : {len(all_discovered_ranges)}")
    print(f"Expected ranges      : {len(expected)}")
    print(f"In-scope ranges      : {len(discovered_ranges)}")
    print(f"Adjacency issues     : {len(adjacency_issues)}")
    print(f"Boundary issues      : {len(boundary_issues)}")
    print(f"Missing ranges       : {len(missing_ranges)}")
    print(f"Extra ranges         : {len(extra_ranges)}")
    print(f"Total topology errors: {total_topology_errors}")

    if adjacency_issues:
        print()
        print("[TOPOLOGY FAIL] Range adjacency problems:")
        for issue in adjacency_issues:
            print(f"  - {issue}")

    if boundary_issues:
        print()
        print("[TOPOLOGY FAIL] Cross-file prime boundary problems:")
        for issue in boundary_issues:
            print(f"  - {issue}")

    if missing_ranges:
        print()
        print("[TOPOLOGY FAIL] Missing expected ranges:")
        for start, end in missing_ranges:
            print(f"  - {start:,} - {end:,}")

    if extra_ranges:
        print()
        print("[TOPOLOGY FAIL] Unexpected extra ranges:")
        for start, end in extra_ranges:
            print(f"  - {start:,} - {end:,}")

    if total_topology_errors == 0:
        print()
        print(
            "[TOPOLOGY PASSED] "
            "Repository range structure and cross-file boundaries are valid."
        )

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
                    "verification_mode": mode,
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
                    "verified_at": datetime.now().isoformat(
                        timespec="seconds"
                    ),
                    "verifier_version": VERIFIER_VERSION,
                }
            )
            continue

        file_size_gb = path.stat().st_size / (1024**3)

        try:
            file_start, file_end = parse_range_from_filename(path)

            if file_start != start or file_end != end:
                raise ValueError("filename_range_mismatch")

            result = verify_array(
                path,
                start,
                end,
                full_scan=full_scan,
            )

            checksum = sha256_file(path) if full_scan else ""
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
                    "verification_mode": mode,
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
                    "verified_at": datetime.now().isoformat(
                        timespec="seconds"
                    ),
                    "verifier_version": VERIFIER_VERSION,
                }
            )

        except Exception as exc:
            total_failed += 1
            print(f"[FAILED] {exc}")

            rows.append(
                {
                    "verification_mode": mode,
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
                    "verified_at": datetime.now().isoformat(
                        timespec="seconds"
                    ),
                    "verifier_version": VERIFIER_VERSION,
                }
            )

    runtime_sec = time.time() - t0

    total_expected = len(expected)
    total_found = total_expected - total_missing

    accepted = (
        total_failed == 0
        and total_missing == 0
        and total_topology_errors == 0
        and total_passed == total_expected
        and total_found == total_expected
    )

    write_manifest(manifest_file, rows)

    write_summary(
        summary_file,
        verification_mode=mode,
        total_expected=total_expected,
        total_discovered=len(discovered_ranges),
        total_found=total_found,
        total_passed=total_passed,
        total_failed=total_failed,
        total_missing=total_missing,
        total_topology_errors=total_topology_errors,
        accepted=accepted,
        runtime_sec=runtime_sec,
        manifest_file=manifest_file,
    )

    print()
    print("=" * 80)
    print("Verification complete.")
    print(f"Mode:            {mode}")
    print(f"Physical:        {len(all_discovered_ranges)}")
    print(f"Expected:        {total_expected}")
    print(f"In scope:        {len(discovered_ranges)}")
    print(f"Found:           {total_found}")
    print(f"Passed:          {total_passed}")
    print(f"Failed:          {total_failed}")
    print(f"Missing:         {total_missing}")
    print(f"Topology errors: {total_topology_errors}")
    print(f"Manifest:        {manifest_file}")
    print(f"Summary:         {summary_file}")
    print("=" * 80)

    if accepted:
        print()
        print("=" * 80)
        print("[ACCEPTED]")
        print(
            f"PrimeNet prime repository satisfies the {mode} "
            "verification contract."
        )
        print("=" * 80)
        return

    print()
    print("=" * 80)
    print("[REJECTED]")
    print("PrimeNet prime repository failed validation.")
    print("Review failed files, missing ranges, and topology errors.")
    print("=" * 80)

    sys.exit(1)


if __name__ == "__main__":
    main()