from pathlib import Path
import subprocess
import sys
import time
import csv
from datetime import datetime

PLATFORM = Path(r"C:\PrimeNet\Platform")
OUT_CSV = Path(r"C:\PrimeNet\Lab\reports\rerun_10_batches_runtime.csv")
OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

BATCHES = [
    (1, 10_000_000_000),
    (90_000_000_001, 100_000_000_000),
    (180_000_000_001, 190_000_000_000),   # previous anomaly
    (300_000_000_001, 310_000_000_000),
    (490_000_000_001, 500_000_000_000),
    (600_000_000_001, 610_000_000_000),
    (750_000_000_001, 760_000_000_000),
    (850_000_000_001, 860_000_000_000),
    (900_000_000_001, 910_000_000_000),
    (990_000_000_001, 1_000_000_000_000),
]

print("=" * 80)
print("PrimeNet Lab - 10 Batch Rerun Test")
print("=" * 80)
print(f"Batches: {len(BATCHES)}")
print("Expected total output: about 30 GB")
print("WARNING: This overwrites the same official repository batch files.")
print("=" * 80)

with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "timestamp",
        "batch_start",
        "batch_end",
        "return_code",
        "runtime_seconds",
        "runtime_minutes",
        "status",
    ])

    for i, (start, end) in enumerate(BATCHES, 1):
        print()
        print("-" * 80)
        print(f"[{i}/{len(BATCHES)}] {start:,} - {end:,}")
        print("-" * 80)

        cmd = [
            sys.executable,
            "-m",
            "core.build_prime_range",
            "--start", str(start),
            "--end", str(end),
            "--overwrite",
        ]

        t0 = time.time()
        result = subprocess.run(cmd, cwd=PLATFORM)
        t1 = time.time()

        runtime_seconds = t1 - t0
        runtime_minutes = runtime_seconds / 60

        if result.returncode == 0 and runtime_minutes <= 10:
            status = "NORMAL"
        elif result.returncode == 0 and runtime_minutes <= 30:
            status = "SLOW"
        elif result.returncode == 0 and runtime_minutes <= 60:
            status = "CRITICAL"
        elif result.returncode == 0:
            status = "ANOMALY_OVER_60_MIN"
        else:
            status = "FAILED"

        writer.writerow([
            datetime.now().isoformat(timespec="seconds"),
            start,
            end,
            result.returncode,
            f"{runtime_seconds:.3f}",
            f"{runtime_minutes:.6f}",
            status,
        ])
        f.flush()

        print()
        print(f"[RESULT] runtime={runtime_minutes:.3f} min status={status}")

print()
print("=" * 80)
print("10 batch rerun test complete.")
print(f"Runtime report: {OUT_CSV}")
print("=" * 80)