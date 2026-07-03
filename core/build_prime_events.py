"""
PrimeNet Prime Event Builder v1.1.0

Canonical Stage 2 event format:
    event = (prime, gap)

For each consecutive prime pair p_i, p_{i+1}, this builder stores:
    prime = p_i
    gap   = p_{i+1} - p_i

The next prime is reconstructible as:
    next_prime = prime + gap

This format is compact, mathematically complete, and observatory-ready.
"""

from __future__ import annotations

import argparse
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

PRIME_EVENT_DTYPE = np.dtype([
    ("prime", np.uint64),
    ("gap", np.uint16),
])


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


def prime_file_name(start: int, end: int) -> str:
    return f"primes_{start}_{end}.npy"


def event_file_name(start: int, end: int) -> str:
    return f"prime_events_{start}_{end}.npy"


def metadata_file_name(start: int, end: int) -> str:
    return f"prime_events_{start}_{end}.json"


def build_prime_events(start: int, end: int, overwrite: bool = False) -> dict:
    input_file = RANGES_DIR / prime_file_name(start, end)
    output_file = PRIME_EVENTS_DIR / event_file_name(start, end)
    metadata_file = METADATA_DIR / metadata_file_name(start, end)

    print("=" * 80)
    print(f"PrimeNet Prime Event Builder v{VERSION}")
    print("=" * 80)
    print(f"Range       = {start:,} - {end:,}")
    print(f"Input file  = {input_file}")
    print(f"Output file = {output_file}")
    print(f"Overwrite   = {overwrite}")
    print("=" * 80)

    if not input_file.exists():
        raise FileNotFoundError(f"Missing input prime file: {input_file}")

    PRIME_EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    if output_file.exists() and not overwrite:
        raise FileExistsError(f"Output exists. Use --overwrite to replace: {output_file}")

    t0 = time.perf_counter()

    print("[LOAD] Loading prime file with memory map...")
    primes = np.load(input_file, mmap_mode="r")

    if primes.ndim != 1:
        raise ValueError(f"Expected 1-D prime array, got shape={primes.shape}")
    if len(primes) < 2:
        raise ValueError("Need at least two primes to build prime events")

    prime_count = int(len(primes))
    event_count = prime_count - 1
    min_prime = int(primes[0])
    max_prime = int(primes[-1])

    print(f"[INFO] prime_count = {prime_count:,}")
    print(f"[INFO] event_count = {event_count:,}")

    print("[BUILD] Computing gaps...")
    gaps64 = np.diff(primes.astype(np.uint64))
    max_gap = int(gaps64.max())
    min_gap = int(gaps64.min())

    if max_gap > np.iinfo(np.uint16).max:
        raise OverflowError(
            f"max_gap={max_gap} exceeds uint16 limit. "
            "Use a wider gap dtype before continuing."
        )

    print("[BUILD] Creating compact prime-event array: dtype=[prime:uint64, gap:uint16]")
    events = np.empty(event_count, dtype=PRIME_EVENT_DTYPE)
    events["prime"] = primes[:-1]
    events["gap"] = gaps64.astype(np.uint16)

    print("[SAVE] Writing prime events...")
    np.save(output_file, events)

    output_size_bytes = output_file.stat().st_size

    print("[HASH] Computing SHA-256...")
    sha256 = sha256_file(output_file)

    runtime_seconds = time.perf_counter() - t0

    metadata = {
        "version": VERSION,
        "status": "PASSED",
        "event_model": "prime_gap",
        "record_definition": "Each record stores prime p and following gap g; next_prime = p + g.",
        "dtype": str(PRIME_EVENT_DTYPE),
        "range_start": start,
        "range_end": end,
        "input_file": str(input_file),
        "output_file": str(output_file),
        "metadata_file": str(metadata_file),
        "prime_count": prime_count,
        "event_count": event_count,
        "min_prime": min_prime,
        "max_prime": max_prime,
        "min_gap": min_gap,
        "max_gap": max_gap,
        "output_size_bytes": output_size_bytes,
        "sha256": sha256,
        "runtime_seconds": runtime_seconds,
        "built_at_utc": utc_now(),
    }

    metadata_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print("=" * 80)
    print("[PASSED]")
    print(f"prime_count = {prime_count:,}")
    print(f"event_count = {event_count:,}")
    print(f"min_gap     = {min_gap:,}")
    print(f"max_gap     = {max_gap:,}")
    print(f"size        = {output_size_bytes / (1024 ** 3):.6f} GB")
    print(f"runtime     = {runtime_seconds:.3f} sec ({runtime_seconds / 60:.3f} min)")
    print(f"metadata    = {metadata_file}")
    print("=" * 80)

    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build compact PrimeNet prime-event files.")
    parser.add_argument("--start", type=int, required=True, help="Range start")
    parser.add_argument("--end", type=int, required=True, help="Range end")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_prime_events(args.start, args.end, args.overwrite)


if __name__ == "__main__":
    main()
