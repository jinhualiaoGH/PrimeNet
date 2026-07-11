"""
PrimeNet Gap Repository Acceptance Audit v2.1.0

Audits the complete index-aligned uint16 gap repository.

Mathematical contract
---------------------
For every stored prime p(i), the corresponding gap file stores

    g(i) = p(i + 1) - p(i)

Therefore, for every partition:

    gap_count == prime_count

Ordinary partition boundary:
    final gap uses the first prime of the next prime file.

Terminal repository boundary:
    final gap uses the independently computed next prime after the
    final stored prime.

Engineering contract
--------------------
1. Repository files are ordered numerically, never lexically.
2. Prime ranges are contiguous.
3. Prime and gap files have one-to-one range correspondence.
4. Every local gap is verified against the prime repository.
5. Every cross-file boundary gap is verified.
6. The terminal outgoing gap is verified independently.
7. Every gap file uses uint16.
8. Manifest records are checked against the physical repository.

Run:
    cd C:\\PrimeNet\\Platform
    py -m core.verify_gap_repository
"""

from __future__ import annotations

import csv
import math
import sys
import time
from pathlib import Path

import numpy as np

from core.range_files import sorted_range_files, validate_adjacency
from core.platform_config import load_platform_config


VERSION = "2.1.0"

CONFIG = load_platform_config()
PATHS = CONFIG.paths
REPOSITORY_EXTENT = CONFIG.repository_extent

REPOSITORY_START = REPOSITORY_EXTENT.start
REPOSITORY_END = REPOSITORY_EXTENT.end

REPOSITORY_ROOT = PATHS.repository_root
PRIME_DIR = PATHS.ranges_dir

# Canonical index-aligned uint16 gap repository.
GAP_DIR = PATHS.gaps_dir

MANIFEST_CSV = (
    PATHS.metadata_dir
    / "gap_repository_u16_v3_manifest.csv"
)

# Number of local gaps checked per memory-mapped block.
# 10 million gaps requires approximately:
#   primes: ~80 MB
#   gaps:   ~20 MB
CHUNK_SIZE = 10_000_000

EXPECTED_DTYPE = np.dtype(np.uint16)


def fmt(n: int) -> str:
    return f"{n:,}"


# ----------------------------------------------------------------------
# Independent 64-bit primality implementation
# ----------------------------------------------------------------------

def is_prime_64(n: int) -> bool:
    """
    Deterministic Miller-Rabin primality test for unsigned 64-bit integers.

    The selected bases are sufficient for every n < 2**64.
    """
    if n < 2:
        return False

    small_primes = (
        2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37
    )

    for p in small_primes:
        if n == p:
            return True
        if n % p == 0:
            return False

    # Write n - 1 as d * 2**s with d odd.
    d = n - 1
    s = 0

    while d % 2 == 0:
        d //= 2
        s += 1

    # Deterministic bases for all unsigned 64-bit integers.
    bases = (
        2,
        325,
        9_375,
        28_178,
        450_775,
        9_780_504,
        1_795_265_022,
    )

    for a in bases:
        if a % n == 0:
            continue

        x = pow(a, d, n)

        if x == 1 or x == n - 1:
            continue

        for _ in range(s - 1):
            x = pow(x, 2, n)

            if x == n - 1:
                break
        else:
            return False

    return True


def next_prime_after(n: int) -> int:
    """
    Return the smallest prime strictly greater than n.
    """
    if n < 2:
        return 2

    candidate = n + 1

    if candidate <= 2:
        return 2

    if candidate % 2 == 0:
        candidate += 1

    while not is_prime_64(candidate):
        candidate += 2

    return candidate


# ----------------------------------------------------------------------
# Manifest support
# ----------------------------------------------------------------------

def load_manifest(path: Path) -> dict[tuple[int, int], dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")

    rows: dict[tuple[int, int], dict[str, str]] = {}

    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row_number, row in enumerate(reader, start=2):
            try:
                start = int(row["range_start"])
                end = int(row["range_end"])
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"Invalid manifest row {row_number}: {row}"
                ) from exc

            key = (start, end)

            if key in rows:
                raise RuntimeError(
                    f"Duplicate manifest range: {start}-{end}"
                )

            rows[key] = row

    return rows


def parse_manifest_bool(value: str | None) -> bool:
    return str(value).strip().lower() in {
        "true", "1", "yes", "y"
    }


# ----------------------------------------------------------------------
# Chunked local-gap verification
# ----------------------------------------------------------------------

def verify_local_gaps(
    primes: np.ndarray,
    gaps: np.ndarray,
    chunk_size: int,
) -> tuple[bool, int | None, int | None, int | None]:
    """
    Verify all within-file gaps in bounded-memory chunks.

    Returns:
        passed,
        mismatch_index,
        expected_gap,
        actual_gap
    """
    local_gap_count = len(primes) - 1

    for start in range(0, local_gap_count, chunk_size):
        stop = min(start + chunk_size, local_gap_count)

        # Need one additional prime to form stop-start differences.
        prime_block = primes[start : stop + 1]
        gap_block = gaps[start:stop]

        expected = prime_block[1:] - prime_block[:-1]

        mismatch_positions = np.flatnonzero(
            expected != gap_block
        )

        if mismatch_positions.size:
            local_offset = int(mismatch_positions[0])
            absolute_index = start + local_offset

            return (
                False,
                absolute_index,
                int(expected[local_offset]),
                int(gap_block[local_offset]),
            )

    return True, None, None, None


# ----------------------------------------------------------------------
# Main audit
# ----------------------------------------------------------------------

def main() -> None:
    audit_t0 = time.perf_counter()

    print("=" * 80)
    print(f"PrimeNet Gap Repository Acceptance Audit v{VERSION}")
    print("=" * 80)
    print(f"Prime directory : {PRIME_DIR}")
    print(f"Gap directory   : {GAP_DIR}")
    print(f"Manifest        : {MANIFEST_CSV}")
    print(
        f"Repository extent: "
        f"{fmt(REPOSITORY_START)} - {fmt(REPOSITORY_END)}"
    )
    print(f"Chunk size      : {fmt(CHUNK_SIZE)} local gaps")
    print()
    print("Repository law:")
    print("  Mathematical coordinate order, never lexical filename order.")
    print("  One stored prime index owns one outgoing gap.")
    print("=" * 80)

    errors = 0
    warnings = 0

    files_passed = 0
    local_gaps_verified = 0
    boundaries_verified = 0
    terminal_boundaries_verified = 0

    total_prime_count = 0
    total_gap_count = 0

    # ------------------------------------------------------------------
    # Discover files using canonical numeric ordering.
    # ------------------------------------------------------------------

    prime_ranges = sorted_range_files(PRIME_DIR, "primes")
    gap_ranges = sorted_range_files(GAP_DIR, "gaps")

    print(f"Prime files discovered : {fmt(len(prime_ranges))}")
    print(f"Gap files discovered   : {fmt(len(gap_ranges))}")

    if not prime_ranges:
        raise RuntimeError(f"No prime files found: {PRIME_DIR}")

    if not gap_ranges:
        raise RuntimeError(f"No gap files found: {GAP_DIR}")

    # ------------------------------------------------------------------
    # Validate canonical physical repository extent.
    # ------------------------------------------------------------------

    first_prime_range = prime_ranges[0]
    last_prime_range = prime_ranges[-1]
    first_gap_range = gap_ranges[0]
    last_gap_range = gap_ranges[-1]

    if first_prime_range.start != REPOSITORY_START:
        print(
            "\n[FAIL] Prime repository start mismatch: "
            f"expected={fmt(REPOSITORY_START)}, "
            f"actual={fmt(first_prime_range.start)}"
        )
        errors += 1

    if last_prime_range.end != REPOSITORY_END:
        print(
            "\n[FAIL] Prime repository end mismatch: "
            f"expected={fmt(REPOSITORY_END)}, "
            f"actual={fmt(last_prime_range.end)}"
        )
        errors += 1

    if first_gap_range.start != REPOSITORY_START:
        print(
            "\n[FAIL] Gap repository start mismatch: "
            f"expected={fmt(REPOSITORY_START)}, "
            f"actual={fmt(first_gap_range.start)}"
        )
        errors += 1

    if last_gap_range.end != REPOSITORY_END:
        print(
            "\n[FAIL] Gap repository end mismatch: "
            f"expected={fmt(REPOSITORY_END)}, "
            f"actual={fmt(last_gap_range.end)}"
        )
        errors += 1

    # ------------------------------------------------------------------
    # Validate numeric adjacency.
    # ------------------------------------------------------------------

    prime_adjacency_issues = validate_adjacency(prime_ranges)
    gap_adjacency_issues = validate_adjacency(gap_ranges)

    if prime_adjacency_issues:
        print("\n[FAIL] Prime range adjacency errors:")
        for issue in prime_adjacency_issues:
            print(f"  {issue}")
        errors += len(prime_adjacency_issues)

    if gap_adjacency_issues:
        print("\n[FAIL] Gap range adjacency errors:")
        for issue in gap_adjacency_issues:
            print(f"  {issue}")
        errors += len(gap_adjacency_issues)

    # ------------------------------------------------------------------
    # Validate exact one-to-one range correspondence.
    # ------------------------------------------------------------------

    prime_map = {
        (rf.start, rf.end): rf
        for rf in prime_ranges
    }

    gap_map = {
        (rf.start, rf.end): rf
        for rf in gap_ranges
    }

    prime_keys = set(prime_map)
    gap_keys = set(gap_map)

    missing_gap_ranges = sorted(prime_keys - gap_keys)
    extra_gap_ranges = sorted(gap_keys - prime_keys)

    if missing_gap_ranges:
        print("\n[FAIL] Missing gap ranges:")
        for start, end in missing_gap_ranges:
            print(f"  {fmt(start)} - {fmt(end)}")
        errors += len(missing_gap_ranges)

    if extra_gap_ranges:
        print("\n[FAIL] Extra gap ranges:")
        for start, end in extra_gap_ranges:
            print(f"  {fmt(start)} - {fmt(end)}")
        errors += len(extra_gap_ranges)

    if errors:
        print("\n[FATAL] Repository structure is not suitable for arithmetic audit.")
        print(f"Structural errors: {fmt(errors)}")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Load and structurally validate manifest.
    # ------------------------------------------------------------------

    manifest_rows = load_manifest(MANIFEST_CSV)
    manifest_keys = set(manifest_rows)

    missing_manifest_ranges = sorted(prime_keys - manifest_keys)
    extra_manifest_ranges = sorted(manifest_keys - prime_keys)

    if missing_manifest_ranges:
        print("\n[FAIL] Missing manifest ranges:")
        for start, end in missing_manifest_ranges:
            print(f"  {fmt(start)} - {fmt(end)}")
        errors += len(missing_manifest_ranges)

    if extra_manifest_ranges:
        print("\n[FAIL] Extra manifest ranges:")
        for start, end in extra_manifest_ranges:
            print(f"  {fmt(start)} - {fmt(end)}")
        errors += len(extra_manifest_ranges)

    # ------------------------------------------------------------------
    # Audit every partition.
    # ------------------------------------------------------------------

    print("\n" + "=" * 80)
    print("Beginning full arithmetic verification")
    print("=" * 80)

    for index, prime_rf in enumerate(prime_ranges):
        file_t0 = time.perf_counter()

        key = (prime_rf.start, prime_rf.end)
        gap_rf = gap_map[key]
        manifest = manifest_rows.get(key)

        file_errors: list[str] = []

        primes = np.load(prime_rf.path, mmap_mode="r")
        gaps = np.load(gap_rf.path, mmap_mode="r")

        prime_count = int(primes.size)
        gap_count = int(gaps.size)

        total_prime_count += prime_count
        total_gap_count += gap_count

        print()
        print("-" * 80)
        print(
            f"[{index + 1}/{len(prime_ranges)}] "
            f"{fmt(prime_rf.start)} - {fmt(prime_rf.end)}"
        )
        print(f"Prime file : {prime_rf.path}")
        print(f"Gap file   : {gap_rf.path}")
        print(f"Primes     : {fmt(prime_count)}")
        print(f"Gaps       : {fmt(gap_count)}")

        # --------------------------------------------------------------
        # Shape and dtype.
        # --------------------------------------------------------------

        if primes.ndim != 1:
            file_errors.append(
                f"prime array is not 1D: shape={primes.shape}"
            )

        if gaps.ndim != 1:
            file_errors.append(
                f"gap array is not 1D: shape={gaps.shape}"
            )

        if primes.dtype != np.dtype(np.uint64):
            file_errors.append(
                f"prime dtype={primes.dtype}, expected=uint64"
            )

        if gaps.dtype != EXPECTED_DTYPE:
            file_errors.append(
                f"gap dtype={gaps.dtype}, expected={EXPECTED_DTYPE}"
            )

        if prime_count < 2:
            file_errors.append(
                f"prime_count={prime_count}, expected at least 2"
            )

        if gap_count != prime_count:
            file_errors.append(
                "gap_count != prime_count: "
                f"{gap_count} != {prime_count}"
            )

        # --------------------------------------------------------------
        # Prime monotonicity and local gaps.
        # The local-gap comparison also verifies strict increase because
        # every stored gap must be positive and equal to the difference.
        # --------------------------------------------------------------

        if not file_errors:
            (
                local_passed,
                mismatch_index,
                expected_gap,
                actual_gap,
            ) = verify_local_gaps(
                primes,
                gaps,
                CHUNK_SIZE,
            )

            if not local_passed:
                file_errors.append(
                    "local gap mismatch at local index "
                    f"{fmt(mismatch_index)}: "
                    f"expected={expected_gap}, actual={actual_gap}, "
                    f"p(i)={int(primes[mismatch_index])}, "
                    f"p(i+1)={int(primes[mismatch_index + 1])}"
                )
            else:
                local_gaps_verified += prime_count - 1

        # --------------------------------------------------------------
        # Boundary gap.
        # --------------------------------------------------------------

        expected_boundary_gap: int | None = None
        next_prime_used: int | None = None
        is_terminal = index == len(prime_ranges) - 1

        if not file_errors:
            last_prime = int(primes[-1])
            actual_boundary_gap = int(gaps[-1])

            if not is_terminal:
                next_prime_rf = prime_ranges[index + 1]
                next_primes = np.load(
                    next_prime_rf.path,
                    mmap_mode="r",
                )

                next_prime_used = int(next_primes[0])
                expected_boundary_gap = (
                    next_prime_used - last_prime
                )

                if actual_boundary_gap != expected_boundary_gap:
                    file_errors.append(
                        "cross-file boundary mismatch: "
                        f"last_prime={last_prime}, "
                        f"next_first_prime={next_prime_used}, "
                        f"expected={expected_boundary_gap}, "
                        f"actual={actual_boundary_gap}"
                    )
                else:
                    boundaries_verified += 1

            else:
                # Independent terminal calculation.
                next_prime_used = next_prime_after(last_prime)
                expected_boundary_gap = (
                    next_prime_used - last_prime
                )

                if actual_boundary_gap != expected_boundary_gap:
                    file_errors.append(
                        "terminal boundary mismatch: "
                        f"last_prime={last_prime}, "
                        f"computed_next_prime={next_prime_used}, "
                        f"expected={expected_boundary_gap}, "
                        f"actual={actual_boundary_gap}"
                    )
                else:
                    terminal_boundaries_verified += 1

        # --------------------------------------------------------------
        # Manifest consistency.
        # --------------------------------------------------------------

        if manifest is None:
            file_errors.append("manifest row missing")
        else:
            manifest_checks = {
                "prime_count": prime_count,
                "gap_count": gap_count,
                "first_prime": int(primes[0]),
                "last_prime": int(primes[-1]),
                "next_prime_used": next_prime_used,
                "boundary_gap": expected_boundary_gap,
            }

            for field, expected_value in manifest_checks.items():
                try:
                    actual_value = int(manifest[field])
                except (KeyError, TypeError, ValueError):
                    file_errors.append(
                        f"invalid manifest field {field!r}: "
                        f"{manifest.get(field)!r}"
                    )
                    continue

                if actual_value != expected_value:
                    file_errors.append(
                        f"manifest {field} mismatch: "
                        f"expected={expected_value}, "
                        f"actual={actual_value}"
                    )

            manifest_terminal = parse_manifest_bool(
                manifest.get("terminal_next_prime_computed")
            )

            if manifest_terminal != is_terminal:
                file_errors.append(
                    "manifest terminal flag mismatch: "
                    f"expected={is_terminal}, "
                    f"actual={manifest_terminal}"
                )

            if manifest.get("dtype") != "uint16":
                file_errors.append(
                    "manifest dtype mismatch: "
                    f"{manifest.get('dtype')!r}"
                )

            if manifest.get("status") != "PASSED":
                file_errors.append(
                    "manifest status is not PASSED: "
                    f"{manifest.get('status')!r}"
                )

            expected_gap_path = str(gap_rf.path)
            expected_prime_path = str(prime_rf.path)

            if manifest.get("gap_file") != expected_gap_path:
                file_errors.append(
                    "manifest gap_file path mismatch"
                )

            if manifest.get("prime_file") != expected_prime_path:
                file_errors.append(
                    "manifest prime_file path mismatch"
                )

        # --------------------------------------------------------------
        # Report file result.
        # --------------------------------------------------------------

        elapsed = time.perf_counter() - file_t0

        if file_errors:
            errors += len(file_errors)

            print("[FAIL]")
            for message in file_errors:
                print(f"  - {message}")
        else:
            files_passed += 1

            print("[PASS]")
            print(
                f"  Local gaps verified : "
                f"{fmt(prime_count - 1)}"
            )
            print(
                f"  Boundary gap        : "
                f"{fmt(expected_boundary_gap)}"
            )
            print(
                f"  Next prime used     : "
                f"{fmt(next_prime_used)}"
            )
            print(
                f"  Terminal            : "
                f"{is_terminal}"
            )

        print(f"  Audit runtime       : {elapsed:.3f} sec")

    # ------------------------------------------------------------------
    # Final summary.
    # ------------------------------------------------------------------

    total_elapsed = time.perf_counter() - audit_t0

    print()
    print("=" * 80)
    print("PrimeNet Gap Repository Acceptance Audit Summary")
    print("=" * 80)
    print(f"Prime files                    : {fmt(len(prime_ranges))}")
    print(f"Gap files                      : {fmt(len(gap_ranges))}")
    print(f"Manifest rows                  : {fmt(len(manifest_rows))}")
    print(f"Files passed                   : {fmt(files_passed)}")
    print(f"Total primes                   : {fmt(total_prime_count)}")
    print(f"Total gaps                     : {fmt(total_gap_count)}")
    print(f"Local gaps verified            : {fmt(local_gaps_verified)}")
    print(f"Ordinary boundaries verified  : {fmt(boundaries_verified)}")
    print(
        f"Terminal boundaries verified  : "
        f"{fmt(terminal_boundaries_verified)}"
    )
    print(f"Warnings                       : {fmt(warnings)}")
    print(f"Errors                         : {fmt(errors)}")
    print(f"Audit runtime                  : {total_elapsed / 60:.3f} min")
    print("=" * 80)

    expected_ordinary_boundaries = len(prime_ranges) - 1

    accepted = (
        errors == 0
        and files_passed == len(prime_ranges)
        and len(prime_ranges) == len(gap_ranges)
        and len(manifest_rows) == len(prime_ranges)
        and prime_ranges[0].start == REPOSITORY_START
        and prime_ranges[-1].end == REPOSITORY_END
        and gap_ranges[0].start == REPOSITORY_START
        and gap_ranges[-1].end == REPOSITORY_END
        and total_prime_count == total_gap_count
        and local_gaps_verified
        == total_prime_count - len(prime_ranges)
        and boundaries_verified
        == expected_ordinary_boundaries
        and terminal_boundaries_verified == 1
    )

    if accepted:
        print()
        print("=" * 80)
        print("[ACCEPTED]")
        print("PrimeNet gaps_u16_v3 satisfies the full index-coordinate contract.")
        print()
        print("For every stored prime index i:")
        print("    g(i) = p(i + 1) - p(i)")
        print()
        print("The physical repository boundaries preserve arithmetic continuity.")
        print("=" * 80)
        return
    else:
        print()
        print("=" * 80)
        print("[REJECTED]")
        print("The repository must not be used for scientific observation.")
        print("Review all failures before rerunning the audit.")
        print("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()