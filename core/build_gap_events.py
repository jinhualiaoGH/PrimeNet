"""
PrimeNet Stage 2
Gap Event Builder v1.0.0

Builds standardized prime-gap event files from verified PrimeNet repository
prime range files.

Input:
    E:\\PrimeNet\\Repository\\ranges\\primes_<start>_<end>.npy

Output:
    E:\\PrimeNet\\Repository\\gap_events\\gap_events_<start>_<end>.npy
    E:\\PrimeNet\\Repository\\gap_events\\metadata\\gap_events_<start>_<end>.json

Each gap event row contains:
    prime_before, prime_after, gap, local_index, range_start, range_end

Notes:
    This file handles gaps fully inside a single prime file.
    Cross-file boundary gaps are handled by drive_gap_event_repository.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


VERSION = "1.0.0"
DEFAULT_REPOSITORY_ROOT = Path(r"E:\PrimeNet\Repository")
EVENT_DTYPE = np.dtype(
    [
        ("prime_before", "<u8"),
        ("prime_after", "<u8"),
        ("gap", "<u8"),
        ("local_index", "<u8"),
        ("range_start", "<u8"),
        ("range_end", "<u8"),
    ]
)


@dataclass
class GapEventBuildSummary:
    version: str
    status: str
    range_start: int
    range_end: int
    input_file: str
    output_file: str
    metadata_file: str
    prime_count: int
    event_count: int
    min_prime: int | None
    max_prime: int | None
    min_gap: int | None
    max_gap: int | None
    output_size_bytes: int
    sha256: str
    runtime_seconds: float
    built_at_utc: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024 * 64) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def parse_range_from_prime_filename(path: Path) -> tuple[int, int]:
    stem = path.stem
    # expected: primes_<start>_<end>
    parts = stem.split("_")
    if len(parts) != 3 or parts[0] != "primes":
        raise ValueError(f"Invalid prime filename format: {path.name}")
    return int(parts[1]), int(parts[2])


def default_input_path(repository_root: Path, start: int, end: int) -> Path:
    return repository_root / "ranges" / f"primes_{start}_{end}.npy"


def default_output_path(repository_root: Path, start: int, end: int) -> Path:
    return repository_root / "gap_events" / f"gap_events_{start}_{end}.npy"


def default_metadata_path(repository_root: Path, start: int, end: int) -> Path:
    return repository_root / "gap_events" / "metadata" / f"gap_events_{start}_{end}.json"


def build_gap_events(
    input_file: Path,
    output_file: Path,
    metadata_file: Path,
    range_start: int,
    range_end: int,
    overwrite: bool = False,
) -> GapEventBuildSummary:
    t0 = time.perf_counter()

    input_file = Path(input_file)
    output_file = Path(output_file)
    metadata_file = Path(metadata_file)

    if not input_file.exists():
        raise FileNotFoundError(f"Input prime file not found: {input_file}")

    if output_file.exists() and not overwrite:
        raise FileExistsError(
            f"Output already exists: {output_file}\n"
            f"Use --overwrite to replace it."
        )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    metadata_file.parent.mkdir(parents=True, exist_ok=True)

    primes = np.load(input_file, mmap_mode="r")
    prime_count = int(primes.shape[0])

    if prime_count == 0:
        events = np.empty(0, dtype=EVENT_DTYPE)
        min_prime = max_prime = min_gap = max_gap = None
    elif prime_count == 1:
        events = np.empty(0, dtype=EVENT_DTYPE)
        min_prime = max_prime = int(primes[0])
        min_gap = max_gap = None
    else:
        before = np.asarray(primes[:-1], dtype=np.uint64)
        after = np.asarray(primes[1:], dtype=np.uint64)
        gaps = after - before
        event_count = len(gaps)

        events = np.empty(event_count, dtype=EVENT_DTYPE)
        events["prime_before"] = before
        events["prime_after"] = after
        events["gap"] = gaps
        events["local_index"] = np.arange(event_count, dtype=np.uint64)
        events["range_start"] = np.uint64(range_start)
        events["range_end"] = np.uint64(range_end)

        min_prime = int(primes[0])
        max_prime = int(primes[-1])
        min_gap = int(gaps.min())
        max_gap = int(gaps.max())

    np.save(output_file, events)
    output_size_bytes = output_file.stat().st_size
    digest = sha256_file(output_file)
    runtime_seconds = time.perf_counter() - t0

    summary = GapEventBuildSummary(
        version=VERSION,
        status="PASSED",
        range_start=int(range_start),
        range_end=int(range_end),
        input_file=str(input_file),
        output_file=str(output_file),
        metadata_file=str(metadata_file),
        prime_count=prime_count,
        event_count=int(len(events)),
        min_prime=min_prime,
        max_prime=max_prime,
        min_gap=min_gap,
        max_gap=max_gap,
        output_size_bytes=int(output_size_bytes),
        sha256=digest,
        runtime_seconds=float(runtime_seconds),
        built_at_utc=utc_now(),
    )

    with metadata_file.open("w", encoding="utf-8") as f:
        json.dump(asdict(summary), f, indent=2)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="PrimeNet Stage 2 gap event builder")
    parser.add_argument("--repository", default=str(DEFAULT_REPOSITORY_ROOT))
    parser.add_argument("--start", type=int, required=False)
    parser.add_argument("--end", type=int, required=False)
    parser.add_argument("--input-file", default=None)
    parser.add_argument("--output-file", default=None)
    parser.add_argument("--metadata-file", default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    repository_root = Path(args.repository)

    if args.input_file:
        input_file = Path(args.input_file)
        parsed_start, parsed_end = parse_range_from_prime_filename(input_file)
        start = args.start if args.start is not None else parsed_start
        end = args.end if args.end is not None else parsed_end
    else:
        if args.start is None or args.end is None:
            raise ValueError("Either --input-file or both --start and --end are required.")
        start, end = args.start, args.end
        input_file = default_input_path(repository_root, start, end)

    output_file = Path(args.output_file) if args.output_file else default_output_path(repository_root, start, end)
    metadata_file = Path(args.metadata_file) if args.metadata_file else default_metadata_path(repository_root, start, end)

    print("=" * 80)
    print(f"PrimeNet Gap Event Builder v{VERSION}")
    print("=" * 80)
    print(f"Range       = {start:,} - {end:,}")
    print(f"Input file  = {input_file}")
    print(f"Output file = {output_file}")
    print(f"Overwrite   = {args.overwrite}")
    print("=" * 80)

    summary = build_gap_events(
        input_file=input_file,
        output_file=output_file,
        metadata_file=metadata_file,
        range_start=start,
        range_end=end,
        overwrite=args.overwrite,
    )

    print("[PASSED]")
    print(f"prime_count = {summary.prime_count:,}")
    print(f"event_count = {summary.event_count:,}")
    print(f"min_gap     = {summary.min_gap}")
    print(f"max_gap     = {summary.max_gap}")
    print(f"size        = {summary.output_size_bytes / (1024 ** 3):.6f} GB")
    print(f"runtime     = {summary.runtime_seconds:.3f} sec ({summary.runtime_seconds / 60:.3f} min)")
    print(f"metadata    = {metadata_file}")


if __name__ == "__main__":
    main()
