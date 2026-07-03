"""
PrimeNet Stage 2
Gap Event Repository Driver v1.0.0

Builds gap-event files for the full verified PrimeNet prime repository.
Also writes cross-file boundary gap events and a repository-level manifest.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from core.build_gap_events import (
    VERSION as BUILDER_VERSION,
    build_gap_events,
    default_input_path,
    default_metadata_path,
    default_output_path,
    sha256_file,
)


VERSION = "1.0.0"
DEFAULT_REPOSITORY_ROOT = Path(r"E:\PrimeNet\Repository")
DEFAULT_START = 1
DEFAULT_END = 1_000_000_000_000
DEFAULT_BATCH_SIZE = 10_000_000_000

BOUNDARY_DTYPE = np.dtype(
    [
        ("left_range_start", "<u8"),
        ("left_range_end", "<u8"),
        ("right_range_start", "<u8"),
        ("right_range_end", "<u8"),
        ("prime_before", "<u8"),
        ("prime_after", "<u8"),
        ("gap", "<u8"),
        ("boundary_index", "<u8"),
    ]
)


@dataclass
class DriverSummary:
    version: str
    builder_version: str
    status: str
    repository_root: str
    range_start: int
    range_end: int
    batch_size: int
    expected_batches: int
    built_batches: int
    skipped_batches: int
    failed_batches: int
    boundary_event_count: int
    total_internal_gap_events: int
    total_gap_events_including_boundaries: int
    runtime_seconds: float
    runtime_minutes: float
    manifest_file: str
    boundary_file: str
    summary_file: str
    built_at_utc: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def iter_ranges(start: int, end: int, batch_size: int):
    current = start
    while current <= end:
        batch_end = min(current + batch_size - 1, end)
        yield current, batch_end
        current = batch_end + 1


def write_boundary_events(repository_root: Path, ranges: list[tuple[int, int]], overwrite: bool) -> tuple[Path, int, str]:
    out_dir = repository_root / "gap_events"
    out_dir.mkdir(parents=True, exist_ok=True)
    boundary_file = out_dir / "gap_events_boundaries.npy"

    if boundary_file.exists() and not overwrite:
        digest = sha256_file(boundary_file)
        existing = np.load(boundary_file, mmap_mode="r")
        return boundary_file, int(existing.shape[0]), digest

    rows = []
    for i in range(len(ranges) - 1):
        left_start, left_end = ranges[i]
        right_start, right_end = ranges[i + 1]
        left_file = default_input_path(repository_root, left_start, left_end)
        right_file = default_input_path(repository_root, right_start, right_end)
        if not left_file.exists() or not right_file.exists():
            continue

        left = np.load(left_file, mmap_mode="r")
        right = np.load(right_file, mmap_mode="r")
        if len(left) == 0 or len(right) == 0:
            continue

        prime_before = int(left[-1])
        prime_after = int(right[0])
        rows.append(
            (
                left_start,
                left_end,
                right_start,
                right_end,
                prime_before,
                prime_after,
                prime_after - prime_before,
                i,
            )
        )

    arr = np.array(rows, dtype=BOUNDARY_DTYPE)
    np.save(boundary_file, arr)
    digest = sha256_file(boundary_file)
    return boundary_file, int(arr.shape[0]), digest


def main() -> None:
    parser = argparse.ArgumentParser(description="PrimeNet Stage 2 gap event repository driver")
    parser.add_argument("--repository", default=str(DEFAULT_REPOSITORY_ROOT))
    parser.add_argument("--start", type=int, default=DEFAULT_START)
    parser.add_argument("--end", type=int, default=DEFAULT_END)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()

    t0 = time.perf_counter()
    repository_root = Path(args.repository)
    ranges = list(iter_ranges(args.start, args.end, args.batch_size))

    metadata_dir = repository_root / "gap_events" / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    manifest_file = metadata_dir / "gap_events_manifest.csv"
    summary_file = metadata_dir / "gap_events_repository_summary.json"

    print("=" * 80)
    print(f"PrimeNet Gap Event Repository Driver v{VERSION}")
    print("=" * 80)
    print(f"Repository root = {repository_root}")
    print(f"Range           = {args.start:,} - {args.end:,}")
    print(f"Batch size      = {args.batch_size:,}")
    print(f"Total batches   = {len(ranges):,}")
    print(f"Overwrite       = {args.overwrite}")
    print(f"Skip existing   = {args.skip_existing}")
    print("=" * 80)

    manifest_rows = []
    built = skipped = failed = 0
    total_internal_events = 0

    for i, (start, end) in enumerate(ranges, start=1):
        input_file = default_input_path(repository_root, start, end)
        output_file = default_output_path(repository_root, start, end)
        metadata_file = default_metadata_path(repository_root, start, end)

        print("\n" + "-" * 80)
        print(f"[BATCH {i}/{len(ranges)}] {start:,} - {end:,}")
        print(f"Input : {input_file}")
        print(f"Output: {output_file}")

        if output_file.exists() and args.skip_existing and not args.overwrite:
            print("[SKIPPED] Existing output found.")
            skipped += 1
            try:
                with metadata_file.open("r", encoding="utf-8") as f:
                    row = json.load(f)
                manifest_rows.append(row)
                total_internal_events += int(row.get("event_count", 0))
            except Exception:
                manifest_rows.append(
                    {
                        "status": "SKIPPED_METADATA_UNAVAILABLE",
                        "range_start": start,
                        "range_end": end,
                        "input_file": str(input_file),
                        "output_file": str(output_file),
                    }
                )
            continue

        try:
            summary = build_gap_events(
                input_file=input_file,
                output_file=output_file,
                metadata_file=metadata_file,
                range_start=start,
                range_end=end,
                overwrite=args.overwrite,
            )
            row = asdict(summary)
            manifest_rows.append(row)
            total_internal_events += summary.event_count
            built += 1
            print(f"[PASSED] events={summary.event_count:,}, max_gap={summary.max_gap}, runtime={summary.runtime_seconds / 60:.3f} min")
        except Exception as exc:
            failed += 1
            row = {
                "version": BUILDER_VERSION,
                "status": "FAILED",
                "range_start": start,
                "range_end": end,
                "input_file": str(input_file),
                "output_file": str(output_file),
                "metadata_file": str(metadata_file),
                "error": repr(exc),
                "built_at_utc": utc_now(),
            }
            manifest_rows.append(row)
            print(f"[FAILED] {exc!r}")

    print("\n" + "-" * 80)
    print("Writing cross-file boundary gap events...")
    boundary_file, boundary_count, boundary_sha256 = write_boundary_events(repository_root, ranges, overwrite=args.overwrite)
    print(f"Boundary file: {boundary_file}")
    print(f"Boundary events: {boundary_count:,}")

    fieldnames = sorted({k for row in manifest_rows for k in row.keys()})
    with manifest_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)

    runtime_seconds = time.perf_counter() - t0
    summary = DriverSummary(
        version=VERSION,
        builder_version=BUILDER_VERSION,
        status="PASSED" if failed == 0 else "FAILED",
        repository_root=str(repository_root),
        range_start=args.start,
        range_end=args.end,
        batch_size=args.batch_size,
        expected_batches=len(ranges),
        built_batches=built,
        skipped_batches=skipped,
        failed_batches=failed,
        boundary_event_count=boundary_count,
        total_internal_gap_events=int(total_internal_events),
        total_gap_events_including_boundaries=int(total_internal_events + boundary_count),
        runtime_seconds=float(runtime_seconds),
        runtime_minutes=float(runtime_seconds / 60),
        manifest_file=str(manifest_file),
        boundary_file=str(boundary_file),
        summary_file=str(summary_file),
        built_at_utc=utc_now(),
    )

    data = asdict(summary)
    data["boundary_sha256"] = boundary_sha256
    with summary_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print("\n" + "=" * 80)
    print("Gap event repository build complete.")
    print(f"Expected batches: {len(ranges)}")
    print(f"Built batches:    {built}")
    print(f"Skipped batches:  {skipped}")
    print(f"Failed batches:   {failed}")
    print(f"Internal events:  {total_internal_events:,}")
    print(f"Boundary events:  {boundary_count:,}")
    print(f"Total events:     {total_internal_events + boundary_count:,}")
    print(f"Manifest:         {manifest_file}")
    print(f"Summary:          {summary_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
