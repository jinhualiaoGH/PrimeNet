"""
PrimeNet Gap Sequence Builder v1.2.0

Builds compact gap-sequence files from verified PrimeNet prime range files.

Canonical compact record:
    index : uint32   local event index within this range file
    gap   : uint16   prime gap following that event

The prime itself can be recovered from the original immutable prime repository
when needed. Most observatories need only index + gap, so this format is much
smaller than full prime-event records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

VERSION = "1.2.0"
REPOSITORY_ROOT = Path(r"E:\PrimeNet\Repository")
RANGES_DIR = REPOSITORY_ROOT / "ranges"
GAP_SEQ_DIR = REPOSITORY_ROOT / "gap_sequences"
METADATA_DIR = GAP_SEQ_DIR / "metadata"

# align=False is important: uint32 + uint16 = exactly 6 bytes/event.
GAP_SEQUENCE_DTYPE = np.dtype([
    ("index", np.uint32),
    ("gap", np.uint16),
], align=False)


def fmt_int(n: int) -> str:
    return f"{n:,}"


def fmt_gb(n_bytes: int) -> str:
    return f"{n_bytes / (1024 ** 3):.6f} GB"


def prime_file_path(start: int, end: int) -> Path:
    return RANGES_DIR / f"primes_{start}_{end}.npy"


def output_file_path(start: int, end: int) -> Path:
    return GAP_SEQ_DIR / f"gap_sequences_{start}_{end}.npy"


def metadata_file_path(start: int, end: int) -> Path:
    return METADATA_DIR / f"gap_sequences_{start}_{end}.json"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024 * 64) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def build_gap_sequences(start: int, end: int, overwrite: bool = False) -> dict:
    t0 = time.perf_counter()

    input_file = prime_file_path(start, end)
    output_file = output_file_path(start, end)
    metadata_file = metadata_file_path(start, end)

    print("=" * 80)
    print(f"PrimeNet Gap Sequence Builder v{VERSION}")
    print("=" * 80)
    print(f"Range       = {fmt_int(start)} - {fmt_int(end)}")
    print(f"Input file  = {input_file}")
    print(f"Output file = {output_file}")
    print(f"Overwrite   = {overwrite}")
    print("=" * 80)

    if not input_file.exists():
        raise FileNotFoundError(f"Input prime file not found: {input_file}")

    if output_file.exists() and not overwrite:
        raise FileExistsError(
            f"Output already exists: {output_file}\n"
            "Use --overwrite to replace it."
        )

    GAP_SEQ_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    print("[LOAD] Loading prime file with memory map...")
    primes = np.load(input_file, mmap_mode="r")

    if primes.ndim != 1:
        raise ValueError(f"Expected 1D prime array, got shape={primes.shape}")
    if primes.dtype != np.uint64:
        print(f"[WARN] Expected uint64 primes, found {primes.dtype}; continuing.")

    prime_count = int(primes.size)
    if prime_count < 2:
        raise ValueError("Need at least two primes to build gap events.")

    event_count = prime_count - 1
    if event_count > np.iinfo(np.uint32).max:
        raise OverflowError(
            f"event_count={event_count} exceeds uint32 local index capacity. "
            "Use a smaller range or switch index dtype to uint64."
        )

    print(f"[INFO] prime_count = {fmt_int(prime_count)}")
    print(f"[INFO] event_count = {fmt_int(event_count)}")
    print("[BUILD] Computing gaps...")

    gaps_u64 = primes[1:] - primes[:-1]
    min_gap = int(np.min(gaps_u64))
    max_gap = int(np.max(gaps_u64))
    if max_gap > np.iinfo(np.uint16).max:
        raise OverflowError(
            f"max_gap={max_gap} exceeds uint16 capacity. "
            "Switch gap dtype to uint32 for this range."
        )

    print("[BUILD] Creating compact gap-sequence array: dtype=[index:uint32, gap:uint16]")
    events = np.empty(event_count, dtype=GAP_SEQUENCE_DTYPE)
    events["index"] = np.arange(event_count, dtype=np.uint32)
    events["gap"] = gaps_u64.astype(np.uint16, copy=False)

    print("[SAVE] Writing gap sequences...")
    np.save(output_file, events)

    output_size = output_file.stat().st_size
    print("[HASH] Computing SHA-256...")
    digest = sha256_file(output_file)

    runtime = time.perf_counter() - t0
    metadata = {
        "version": VERSION,
        "repository_layer": "gap_sequences",
        "event_format": "GapSequence-v1",
        "status": "PASSED",
        "range_start": start,
        "range_end": end,
        "index_type": "local_zero_based",
        "dtype": {
            "index": "uint32",
            "gap": "uint16",
            "itemsize_bytes": int(GAP_SEQUENCE_DTYPE.itemsize),
            "align": False,
        },
        "input_file": str(input_file),
        "output_file": str(output_file),
        "metadata_file": str(metadata_file),
        "prime_count": prime_count,
        "event_count": event_count,
        "min_prime": int(primes[0]),
        "max_prime": int(primes[-1]),
        "min_gap": min_gap,
        "max_gap": max_gap,
        "output_size_bytes": output_size,
        "sha256": digest,
        "runtime_seconds": runtime,
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    with metadata_file.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("=" * 80)
    print("[PASSED]")
    print(f"prime_count = {fmt_int(prime_count)}")
    print(f"event_count = {fmt_int(event_count)}")
    print(f"min_gap     = {fmt_int(min_gap)}")
    print(f"max_gap     = {fmt_int(max_gap)}")
    print(f"itemsize    = {GAP_SEQUENCE_DTYPE.itemsize} bytes/event")
    print(f"size        = {fmt_gb(output_size)}")
    print(f"runtime     = {runtime:.3f} sec ({runtime / 60:.3f} min)")
    print(f"metadata    = {metadata_file}")
    print("=" * 80)

    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build compact PrimeNet gap-sequence file.")
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_gap_sequences(args.start, args.end, args.overwrite)


if __name__ == "__main__":
    main()
