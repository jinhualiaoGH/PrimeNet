"""
PrimeNet Prime Event Repository Verifier v1.1.0

Verifies compact prime-event files:
    dtype fields: prime:uint64, gap:uint16
    event_count = prime_count - 1
    prime + gap reconstructs next prime for sampled/full checks
    SHA-256 matches metadata
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

VERSION = "1.1.0"

REPOSITORY_ROOT = Path(r"E:\PrimeNet\Repository")
RANGES_DIR = REPOSITORY_ROOT / "ranges"
PRIME_EVENTS_DIR = REPOSITORY_ROOT / "prime_events"
METADATA_DIR = PRIME_EVENTS_DIR / "metadata"
SUMMARY_FILE = PRIME_EVENTS_DIR / "prime_event_verification_summary.txt"
MANIFEST_FILE = PRIME_EVENTS_DIR / "prime_event_manifest.csv"

DEFAULT_START = 1
DEFAULT_END = 1_000_000_000_000
DEFAULT_BATCH_SIZE = 10_000_000_000


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path, chunk_size: int = 64 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def iter_ranges(start: int, end: int, batch_size: int):
    current = start
    while current <= end:
        batch_end = min(current + batch_size - 1, end)
        yield current, batch_end
        current = batch_end + 1


def verify_one(start: int, end: int, full_check: bool = False) -> dict:
    prime_file = RANGES_DIR / f"primes_{start}_{end}.npy"
    event_file = PRIME_EVENTS_DIR / f"prime_events_{start}_{end}.npy"
    metadata_file = METADATA_DIR / f"prime_events_{start}_{end}.json"

    result = {
        "range_start": start,
        "range_end": end,
        "prime_file": str(prime_file),
        "event_file": str(event_file),
        "metadata_file": str(metadata_file),
        "status": "FAILED",
        "reason": "",
        "prime_count": None,
        "event_count": None,
        "min_gap": None,
        "max_gap": None,
        "size_bytes": None,
        "sha256": None,
    }

    if not prime_file.exists():
        result["reason"] = "missing prime file"
        return result
    if not event_file.exists():
        result["reason"] = "missing event file"
        return result
    if not metadata_file.exists():
        result["reason"] = "missing metadata file"
        return result

    primes = np.load(prime_file, mmap_mode="r")
    events = np.load(event_file, mmap_mode="r")
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))

    if "prime" not in events.dtype.names or "gap" not in events.dtype.names:
        result["reason"] = f"bad dtype fields: {events.dtype}"
        return result

    prime_count = int(len(primes))
    event_count = int(len(events))

    result["prime_count"] = prime_count
    result["event_count"] = event_count
    result["size_bytes"] = event_file.stat().st_size

    if event_count != prime_count - 1:
        result["reason"] = "event_count != prime_count - 1"
        return result

    if event_count == 0:
        result["reason"] = "empty event file"
        return result

    min_gap = int(events["gap"].min())
    max_gap = int(events["gap"].max())
    result["min_gap"] = min_gap
    result["max_gap"] = max_gap

    if int(events["prime"][0]) != int(primes[0]):
        result["reason"] = "first event prime mismatch"
        return result
    if int(events["prime"][-1]) != int(primes[-2]):
        result["reason"] = "last event prime mismatch"
        return result

    if full_check:
        reconstructed = events["prime"].astype(np.uint64) + events["gap"].astype(np.uint64)
        if not np.array_equal(reconstructed, primes[1:].astype(np.uint64)):
            result["reason"] = "full reconstruction check failed"
            return result
    else:
        sample_idx = np.linspace(0, event_count - 1, num=min(1000, event_count), dtype=np.int64)
        reconstructed = events["prime"][sample_idx].astype(np.uint64) + events["gap"][sample_idx].astype(np.uint64)
        expected = primes[1:][sample_idx].astype(np.uint64)
        if not np.array_equal(reconstructed, expected):
            result["reason"] = "sample reconstruction check failed"
            return result

    sha256 = sha256_file(event_file)
    result["sha256"] = sha256

    if metadata.get("sha256") != sha256:
        result["reason"] = "sha256 mismatch"
        return result

    if metadata.get("event_count") != event_count:
        result["reason"] = "metadata event_count mismatch"
        return result

    result["status"] = "PASSED"
    result["reason"] = ""
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify compact PrimeNet prime-event repository.")
    parser.add_argument("--start", type=int, default=DEFAULT_START)
    parser.add_argument("--end", type=int, default=DEFAULT_END)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--full-check", action="store_true", help="Check every reconstructed next prime")
    args = parser.parse_args()

    ranges = list(iter_ranges(args.start, args.end, args.batch_size))
    t0 = time.perf_counter()

    print("=" * 80)
    print(f"PrimeNet Prime Event Repository Verifier v{VERSION}")
    print("=" * 80)
    print(f"Repository root = {REPOSITORY_ROOT}")
    print(f"Prime events    = {PRIME_EVENTS_DIR}")
    print(f"Total ranges    = {len(ranges)}")
    print(f"Full check      = {args.full_check}")
    print("=" * 80)

    results = []
    for i, (start, end) in enumerate(ranges, start=1):
        print()
        print("-" * 80)
        print(f"[{i}/{len(ranges)}] {start:,} - {end:,}")
        r = verify_one(start, end, full_check=args.full_check)
        results.append(r)
        if r["status"] == "PASSED":
            print(f"[PASSED] events={r['event_count']:,}, min_gap={r['min_gap']}, max_gap={r['max_gap']}, size={r['size_bytes'] / (1024 ** 3):.6f} GB")
        else:
            print(f"[FAILED] {r['reason']}")

    passed = sum(1 for r in results if r["status"] == "PASSED")
    failed = len(results) - passed
    runtime = time.perf_counter() - t0

    with MANIFEST_FILE.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "range_start", "range_end", "status", "reason", "prime_count", "event_count",
            "min_gap", "max_gap", "size_bytes", "sha256", "event_file", "metadata_file"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k) for k in fieldnames})

    summary = f"""PrimeNet Prime Event Repository Verification Summary
====================================================

Verified at: {utc_now()}
Verifier version: {VERSION}

Repository root: {REPOSITORY_ROOT}
Prime events directory: {PRIME_EVENTS_DIR}

Configured start: {args.start}
Configured end: {args.end}
Batch size: {args.batch_size}
Full check: {args.full_check}

Expected files: {len(ranges)}
Passed files: {passed}
Failed files: {failed}

Runtime seconds: {runtime:.3f}
Runtime minutes: {runtime / 60:.6f}

Manifest:
{MANIFEST_FILE}
"""
    SUMMARY_FILE.write_text(summary, encoding="utf-8")

    print()
    print("=" * 80)
    print("Verification complete.")
    print(f"Expected: {len(ranges)}")
    print(f"Passed:   {passed}")
    print(f"Failed:   {failed}")
    print(f"Manifest: {MANIFEST_FILE}")
    print(f"Summary:  {SUMMARY_FILE}")
    print("=" * 80)


if __name__ == "__main__":
    main()
