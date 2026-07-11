"""
PrimeNet Twin Prime Census v1.0.0

First scientific observation from the accepted PrimeNet
index-aligned gap repository.

Twin-prime event:
    g(i) = 2

Input:
    Accepted gaps_u16_v3 repository, 1 through 3T.

Outputs:
    CSV partition census
    JSON summary

Scientific rule:
    Observation begins only after repository acceptance.
"""

from __future__ import annotations

import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from Platform.core.range_files import sorted_range_files


VERSION = "1.0.0"

REPOSITORY_ROOT = Path(r"E:\PrimeNet\Repository")
GAP_DIR = REPOSITORY_ROOT / "gaps_u16_v3"

OUTPUT_DIR = REPOSITORY_ROOT / "observations" / "twin_primes"

CENSUS_CSV = OUTPUT_DIR / "twin_prime_census_1_3T.csv"
SUMMARY_JSON = OUTPUT_DIR / "twin_prime_census_1_3T_summary.json"

EXPECTED_GAP_FILES = 300
EXPECTED_TOTAL_GAPS = 108_340_298_703

TWIN_GAP = 2


def fmt(n: int) -> str:
    return f"{n:,}"


def main() -> None:
    t_all = time.perf_counter()

    print("=" * 80)
    print(f"PrimeNet Twin Prime Census v{VERSION}")
    print("=" * 80)
    print("Scientific observable : twin-prime events")
    print("Event definition      : g(i) = 2")
    print("Repository            : accepted gaps_u16_v3")
    print("Numeric domain        : 1 - 3,000,000,000,000")
    print("=" * 80)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    gap_files = sorted_range_files(GAP_DIR, "gaps")

    if len(gap_files) != EXPECTED_GAP_FILES:
        raise RuntimeError(
            f"Expected {EXPECTED_GAP_FILES} gap files, "
            f"found {len(gap_files)}"
        )

    rows = []

    total_gaps = 0
    total_twins = 0

    print(f"Gap files discovered  : {fmt(len(gap_files))}")
    print("=" * 80)

    for index, rf in enumerate(gap_files, start=1):
        t0 = time.perf_counter()

        gaps = np.load(rf.path, mmap_mode="r")

        gap_count = int(gaps.size)
        twin_count = int(np.count_nonzero(gaps == TWIN_GAP))

        total_gaps += gap_count
        total_twins += twin_count

        twin_density = twin_count / gap_count
        cumulative_density = total_twins / total_gaps

        runtime_sec = time.perf_counter() - t0

        row = {
            "partition": index,
            "range_start": rf.start,
            "range_end": rf.end,
            "gap_count": gap_count,
            "twin_count": twin_count,
            "twin_density": twin_density,
            "cumulative_gap_count": total_gaps,
            "cumulative_twin_count": total_twins,
            "cumulative_twin_density": cumulative_density,
            "runtime_sec": runtime_sec,
        }

        rows.append(row)

        print(
            f"[{index:3d}/{len(gap_files)}] "
            f"{fmt(rf.start)} - {fmt(rf.end)}  "
            f"gaps={fmt(gap_count)}  "
            f"twins={fmt(twin_count)}  "
            f"density={twin_density:.12f}  "
            f"runtime={runtime_sec:.3f}s"
        )

    # ------------------------------------------------------------------
    # Repository count contract
    # ------------------------------------------------------------------

    if total_gaps != EXPECTED_TOTAL_GAPS:
        raise RuntimeError(
            "Accepted repository count mismatch:\n"
            f"Expected gaps : {fmt(EXPECTED_TOTAL_GAPS)}\n"
            f"Observed gaps : {fmt(total_gaps)}"
        )

    # ------------------------------------------------------------------
    # Write CSV
    # ------------------------------------------------------------------

    csv_fields = [
        "partition",
        "range_start",
        "range_end",
        "gap_count",
        "twin_count",
        "twin_density",
        "cumulative_gap_count",
        "cumulative_twin_count",
        "cumulative_twin_density",
        "runtime_sec",
    ]

    with CENSUS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows(rows)

    # ------------------------------------------------------------------
    # Final summary
    # ------------------------------------------------------------------

    total_runtime_sec = time.perf_counter() - t_all
    global_twin_density = total_twins / total_gaps

    summary = {
        "project": "PrimeNet",
        "instrument": "Twin Prime Census",
        "version": VERSION,
        "repository": str(GAP_DIR),
        "repository_status": "ACCEPTED",
        "numeric_domain_start": 1,
        "numeric_domain_end": 3_000_000_000_000,
        "event_definition": "g(i) = 2",
        "gap_files_scanned": len(gap_files),
        "total_gaps_scanned": total_gaps,
        "total_twin_prime_events": total_twins,
        "global_twin_density": global_twin_density,
        "runtime_seconds": total_runtime_sec,
        "runtime_minutes": total_runtime_sec / 60.0,
        "csv_output": str(CENSUS_CSV),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    with SUMMARY_JSON.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print()
    print("=" * 80)
    print("PrimeNet 1-3T Twin Prime Census Summary")
    print("=" * 80)
    print(f"Gap files scanned       : {fmt(len(gap_files))}")
    print(f"Total gaps scanned      : {fmt(total_gaps)}")
    print(f"Twin-prime events       : {fmt(total_twins)}")
    print(f"Global twin density     : {global_twin_density:.12f}")
    print(f"Runtime                 : {total_runtime_sec / 60.0:.3f} min")
    print(f"Partition census        : {CENSUS_CSV}")
    print(f"Summary                 : {SUMMARY_JSON}")
    print("=" * 80)

    print()
    print("[COMPLETE]")
    print("PrimeNet 1-3T Twin Prime Census completed successfully.")


if __name__ == "__main__":
    main()
