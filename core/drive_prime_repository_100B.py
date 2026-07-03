"""
PrimeNet Repository Driver - 100B Big Batches
Builds prime repository from 1 to 1,000,000,000,000 in 10 batches.
Each batch covers 100B integers and writes one .npy file.
"""

from __future__ import annotations

import csv
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


REPOSITORY_ROOT = Path(r"E:\PrimeNet\Repository")
LOG_DIR = REPOSITORY_ROOT / "logs"

N_START = 1
N_END = 1_000_000_000_000
BIG_BATCH_SIZE = 100_000_000_000

OVERWRITE = True
SKIP_EXISTING = False

RUNTIME_LOG = LOG_DIR / "builder_runtime_100B.csv"


def fmt(n: int) -> str:
    return f"{n:,}"


def append_runtime_log(row: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    write_header = not RUNTIME_LOG.exists()

    with RUNTIME_LOG.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp",
                "batch_index",
                "total_batches",
                "start",
                "end",
                "runtime_sec",
                "runtime_min",
                "status",
            ],
        )
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def main() -> None:
    total_batches = (N_END - N_START + 1 + BIG_BATCH_SIZE - 1) // BIG_BATCH_SIZE

    print("=" * 80)
    print("PrimeNet Repository Driver - 100B Big Batches")
    print("=" * 80)
    print(f"Repository root = {REPOSITORY_ROOT}")
    print(f"Range           = {fmt(N_START)} - {fmt(N_END)}")
    print(f"Batch size      = {fmt(BIG_BATCH_SIZE)}")
    print(f"Total batches   = {total_batches}")
    print(f"Overwrite       = {OVERWRITE}")
    print(f"Skip existing   = {SKIP_EXISTING}")
    print(f"Runtime log     = {RUNTIME_LOG}")
    print("=" * 80)

    for i in range(total_batches):
        start = N_START + i * BIG_BATCH_SIZE
        end = min(start + BIG_BATCH_SIZE - 1, N_END)

        print()
        print("-" * 80)
        print(f"[BIG BATCH {i + 1}/{total_batches}]")
        print(f"Range: {fmt(start)} - {fmt(end)}")
        print("-" * 80)

        cmd = [
            sys.executable,
            "-m",
            "core.build_prime_range",
            "--start",
            str(start),
            "--end",
            str(end),
        ]

        if OVERWRITE:
            cmd.append("--overwrite")

        if SKIP_EXISTING:
            cmd.append("--skip-existing")

        t0 = time.time()
        status = "PASSED"

        try:
            result = subprocess.run(cmd, check=False)
            if result.returncode != 0:
                status = f"FAILED_RETURN_CODE_{result.returncode}"
                print(f"[FAILED] return code = {result.returncode}")
                break
        except Exception as exc:
            status = f"FAILED_EXCEPTION_{type(exc).__name__}"
            print(f"[FAILED] {exc}")
            break
        finally:
            runtime_sec = time.time() - t0
            runtime_min = runtime_sec / 60.0

            append_runtime_log(
                {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "batch_index": i + 1,
                    "total_batches": total_batches,
                    "start": start,
                    "end": end,
                    "runtime_sec": f"{runtime_sec:.3f}",
                    "runtime_min": f"{runtime_min:.3f}",
                    "status": status,
                }
            )

            print(f"[RUNTIME] batch {i + 1}: {runtime_sec:.3f} sec ({runtime_min:.3f} min)")
            print(f"[STATUS] {status}")

    print()
    print("=" * 80)
    print("100B Big Batch Driver Complete")
    print("=" * 80)


if __name__ == "__main__":
    main()