"""
PrimeNet Stage 2
Gap Event Repository Verifier v1.0.0

Verifies standardized gap-event files generated from the PrimeNet repository.
Checks:
    - expected gap-event files exist
    - structured dtype fields are present
    - event_count == prime_count - 1 for each internal file
    - prime_after - prime_before == gap
    - local_index is contiguous
    - range_start/range_end fields match filename range
    - SHA-256 checksums are written to verification manifest
    - boundary gap file has expected count when present
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from core.build_gap_events import EVENT_DTYPE, default_input_path, default_output_path, sha256_file
from core.drive_gap_event_repository import DEFAULT_BATCH_SIZE, DEFAULT_END, DEFAULT_REPOSITORY_ROOT, DEFAULT_START, iter_ranges


VERSION = "1.0.0"
REQUIRED_FIELDS = set(EVENT_DTYPE.names or [])


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def verify_one(repository_root: Path, start: int, end: int) -> dict:
    input_file = default_input_path(repository_root, start, end)
    event_file = default_output_path(repository_root, start, end)

    row = {
        "range_start": start,
        "range_end": end,
        "input_file": str(input_file),
        "event_file": str(event_file),
        "status": "FAILED",
        "error": "",
    }

    if not input_file.exists():
        row["error"] = "missing input prime file"
        return row
    if not event_file.exists():
        row["error"] = "missing gap event file"
        return row

    primes = np.load(input_file, mmap_mode="r")
    events = np.load(event_file, mmap_mode="r")

    prime_count = int(primes.shape[0])
    expected_events = max(prime_count - 1, 0)
    event_count = int(events.shape[0])

    row["prime_count"] = prime_count
    row["expected_event_count"] = expected_events
    row["event_count"] = event_count
    row["event_size_bytes"] = event_file.stat().st_size
    row["sha256"] = sha256_file(event_file)

    if set(events.dtype.names or []) != REQUIRED_FIELDS:
        row["error"] = f"invalid dtype fields: {events.dtype.names}"
        return row

    if event_count != expected_events:
        row["error"] = f"event_count mismatch: expected {expected_events}, found {event_count}"
        return row

    if event_count > 0:
        if not np.all(events["prime_after"] - events["prime_before"] == events["gap"]):
            row["error"] = "gap arithmetic mismatch"
            return row
        if not np.all(events["local_index"] == np.arange(event_count, dtype=np.uint64)):
            row["error"] = "local_index mismatch"
            return row
        if not np.all(events["range_start"] == np.uint64(start)):
            row["error"] = "range_start field mismatch"
            return row
        if not np.all(events["range_end"] == np.uint64(end)):
            row["error"] = "range_end field mismatch"
            return row
        if int(events[0]["prime_before"]) != int(primes[0]):
            row["error"] = "first prime_before mismatch"
            return row
        if int(events[-1]["prime_after"]) != int(primes[-1]):
            row["error"] = "last prime_after mismatch"
            return row
        row["min_gap"] = int(events["gap"].min())
        row["max_gap"] = int(events["gap"].max())
    else:
        row["min_gap"] = ""
        row["max_gap"] = ""

    row["status"] = "PASSED"
    return row


def verify_boundary_file(repository_root: Path, expected_count: int) -> dict:
    boundary_file = repository_root / "gap_events" / "gap_events_boundaries.npy"
    row = {
        "boundary_file": str(boundary_file),
        "expected_count": expected_count,
        "status": "FAILED",
        "error": "",
    }
    if not boundary_file.exists():
        row["error"] = "missing boundary file"
        return row
    arr = np.load(boundary_file, mmap_mode="r")
    row["event_count"] = int(arr.shape[0])
    row["size_bytes"] = boundary_file.stat().st_size
    row["sha256"] = sha256_file(boundary_file)
    if int(arr.shape[0]) != expected_count:
        row["error"] = f"boundary count mismatch: expected {expected_count}, found {arr.shape[0]}"
        return row
    if int(arr.shape[0]) > 0 and not np.all(arr["prime_after"] - arr["prime_before"] == arr["gap"]):
        row["error"] = "boundary gap arithmetic mismatch"
        return row
    row["status"] = "PASSED"
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="PrimeNet Stage 2 gap event verifier")
    parser.add_argument("--repository", default=str(DEFAULT_REPOSITORY_ROOT))
    parser.add_argument("--start", type=int, default=DEFAULT_START)
    parser.add_argument("--end", type=int, default=DEFAULT_END)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()

    t0 = time.perf_counter()
    repository_root = Path(args.repository)
    ranges = list(iter_ranges(args.start, args.end, args.batch_size))
    metadata_dir = repository_root / "gap_events" / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    manifest_file = metadata_dir / "gap_events_verification_manifest.csv"
    summary_file = metadata_dir / "gap_events_verification_summary.txt"
    boundary_summary_file = metadata_dir / "gap_events_boundary_verification.json"

    print("=" * 80)
    print(f"PrimeNet Gap Event Repository Verifier v{VERSION}")
    print("=" * 80)
    print(f"Repository root = {repository_root}")
    print(f"Range           = {args.start:,} - {args.end:,}")
    print(f"Batch size      = {args.batch_size:,}")
    print(f"Expected files  = {len(ranges):,}")
    print("=" * 80)

    rows = []
    passed = failed = 0
    total_events = 0

    for i, (start, end) in enumerate(ranges, start=1):
        print("\n" + "-" * 80)
        print(f"[{i}/{len(ranges)}] {start:,} - {end:,}")
        row = verify_one(repository_root, start, end)
        rows.append(row)
        if row["status"] == "PASSED":
            passed += 1
            total_events += int(row["event_count"])
            print(f"[PASSED] events={int(row['event_count']):,}, max_gap={row['max_gap']}")
        else:
            failed += 1
            print(f"[FAILED] {row['error']}")

    boundary = verify_boundary_file(repository_root, expected_count=max(len(ranges) - 1, 0))
    with boundary_summary_file.open("w", encoding="utf-8") as f:
        json.dump(boundary, f, indent=2)

    if boundary["status"] == "PASSED":
        total_with_boundary = total_events + int(boundary["event_count"])
    else:
        total_with_boundary = total_events

    fieldnames = sorted({k for row in rows for k in row.keys()})
    with manifest_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    runtime_seconds = time.perf_counter() - t0
    text = f"""PrimeNet Gap Event Repository Verification Summary
==================================================

Verified at: {utc_now()}
Verifier version: {VERSION}

Repository root: {repository_root}
Configured start: {args.start}
Configured end: {args.end}
Batch size: {args.batch_size}

Expected internal files: {len(ranges)}
Passed internal files: {passed}
Failed internal files: {failed}
Boundary status: {boundary['status']}
Boundary events: {boundary.get('event_count', 0)}

Internal gap events: {total_events}
Total gap events including boundaries: {total_with_boundary}

Runtime seconds: {runtime_seconds:.3f}
Runtime minutes: {runtime_seconds / 60:.6f}

Manifest:
{manifest_file}
Boundary verification:
{boundary_summary_file}
"""
    summary_file.write_text(text, encoding="utf-8")

    print("\n" + "=" * 80)
    print("Verification complete.")
    print(f"Expected internal files: {len(ranges)}")
    print(f"Passed internal files:   {passed}")
    print(f"Failed internal files:   {failed}")
    print(f"Boundary status:         {boundary['status']}")
    print(f"Internal events:         {total_events:,}")
    print(f"Total with boundaries:   {total_with_boundary:,}")
    print(f"Manifest:                {manifest_file}")
    print(f"Summary:                 {summary_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
