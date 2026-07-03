"""PrimeNet Gap Sequence Verifier v1.2.0"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

VERSION = "1.2.0"
REPOSITORY_ROOT = Path(r"E:\PrimeNet\Repository")
RANGES_DIR = REPOSITORY_ROOT / "ranges"
GAP_SEQ_DIR = REPOSITORY_ROOT / "gap_sequences"
METADATA_DIR = GAP_SEQ_DIR / "metadata"

EXPECTED_DTYPE = np.dtype([("index", np.uint32), ("gap", np.uint16)], align=False)


def fmt_int(n: int) -> str:
    return f"{n:,}"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024 * 64) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def verify_gap_sequences(start: int, end: int) -> dict:
    t0 = time.perf_counter()
    prime_file = RANGES_DIR / f"primes_{start}_{end}.npy"
    seq_file = GAP_SEQ_DIR / f"gap_sequences_{start}_{end}.npy"
    meta_file = METADATA_DIR / f"gap_sequences_{start}_{end}.json"

    print("=" * 80)
    print(f"PrimeNet Gap Sequence Verifier v{VERSION}")
    print("=" * 80)
    print(f"Range       = {fmt_int(start)} - {fmt_int(end)}")
    print(f"Prime file  = {prime_file}")
    print(f"Seq file    = {seq_file}")
    print(f"Metadata    = {meta_file}")
    print("=" * 80)

    if not prime_file.exists():
        raise FileNotFoundError(prime_file)
    if not seq_file.exists():
        raise FileNotFoundError(seq_file)
    if not meta_file.exists():
        raise FileNotFoundError(meta_file)

    with meta_file.open("r", encoding="utf-8") as f:
        meta = json.load(f)

    primes = np.load(prime_file, mmap_mode="r")
    seq = np.load(seq_file, mmap_mode="r")

    errors = []
    if seq.dtype != EXPECTED_DTYPE:
        errors.append(f"dtype mismatch: {seq.dtype} != {EXPECTED_DTYPE}")
    if seq.size != primes.size - 1:
        errors.append(f"event_count mismatch: {seq.size} != {primes.size - 1}")
    if int(seq["index"][0]) != 0:
        errors.append("first index is not 0")
    if int(seq["index"][-1]) != seq.size - 1:
        errors.append("last index mismatch")

    # Full gap validation, still memory efficient via mmap-backed operands.
    print("[CHECK] Validating gaps against prime repository...")
    expected_gaps = primes[1:] - primes[:-1]
    if not np.array_equal(seq["gap"], expected_gaps.astype(np.uint16)):
        errors.append("gap sequence does not match prime differences")

    print("[HASH] Computing SHA-256...")
    digest = sha256_file(seq_file)
    if digest != meta.get("sha256"):
        errors.append("sha256 mismatch")

    runtime = time.perf_counter() - t0
    status = "PASSED" if not errors else "FAILED"

    print("=" * 80)
    print(f"[{status}]")
    print(f"events  = {fmt_int(seq.size)}")
    print(f"min_gap = {fmt_int(int(np.min(seq['gap'])))}")
    print(f"max_gap = {fmt_int(int(np.max(seq['gap'])))}")
    print(f"runtime = {runtime:.3f} sec ({runtime / 60:.3f} min)")
    if errors:
        print("Errors:")
        for err in errors:
            print(f"  - {err}")
    print("=" * 80)

    return {"status": status, "errors": errors, "runtime_seconds": runtime}


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify compact PrimeNet gap-sequence file.")
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    args = parser.parse_args()
    verify_gap_sequences(args.start, args.end)


if __name__ == "__main__":
    main()
