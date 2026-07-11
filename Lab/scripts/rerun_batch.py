"""
PrimeNet Lab
Single Batch Rerun

Usage:

    py rerun_batch.py

This script reruns a single repository batch using the
existing production builder.

The output is written into the Lab so the production
repository is never modified.
"""

from pathlib import Path
import subprocess
import sys

# ============================================================
# Configuration
# ============================================================

PLATFORM = Path(r"C:\PrimeNet\Platform")

N_START = 180_000_000_001
N_END   = 190_000_000_000

print("=" * 72)
print("PrimeNet Lab")
print("Single Batch Rerun")
print("=" * 72)

print()
print(f"Range : {N_START:,} - {N_END:,}")
print()

cmd = [
    sys.executable,
    "-m",
    "core.build_prime_range",
    "--start", str(N_START),
    "--end", str(N_END),
    "--overwrite",
]

print("Executing:")
print()
print(" ".join(cmd))
print()

result = subprocess.run(
    cmd,
    cwd=PLATFORM
)

print()
print("=" * 72)
print("Return Code:", result.returncode)
print("=" * 72)

if result.returncode == 0:
    print()
    print("SUCCESS")
else:
    print()
    print("FAILED")