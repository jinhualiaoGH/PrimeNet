"""
PrimeNet Repository Finalizer v1.3.0

Creates:
- repository_statistics.json
- repository_hashes.csv
- repository_performance.json
- repository_release_report.txt

Run:
    cd C:\\PrimeNet\\Platform
    py -m core.finalize_repository
"""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import statistics
import sys
from datetime import datetime
from pathlib import Path


REPOSITORY_ROOT = Path(r"E:\PrimeNet\Repository")
RANGES_DIR = REPOSITORY_ROOT / "ranges"
METADATA_DIR = REPOSITORY_ROOT / "metadata"
LOGS_DIR = REPOSITORY_ROOT / "logs"

MANIFEST_CSV = METADATA_DIR / "repository_manifest.csv"
PRIME_COUNTS_CSV = METADATA_DIR / "prime_counts.csv"
INVENTORY_CSV = METADATA_DIR / "prime_inventory.csv"
RUNTIME_CSV = LOGS_DIR / "builder_runtime.csv"
VERIFY_SUMMARY = METADATA_DIR / "repository_verification_summary.txt"

STATISTICS_JSON = METADATA_DIR / "repository_statistics.json"
HASHES_CSV = METADATA_DIR / "repository_hashes.csv"
PERFORMANCE_JSON = METADATA_DIR / "repository_performance.json"
RELEASE_REPORT = METADATA_DIR / "repository_release_report.txt"

REPOSITORY_VERSION = "1.3.0"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024 * 64) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def parse_float(row: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except Exception:
        return default


def main() -> None:
    print("=" * 80)
    print("PrimeNet Repository Finalizer v1.3.0")
    print("=" * 80)

    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(RANGES_DIR.glob("primes_*.npy"))

    if not files:
        raise RuntimeError(f"No repository files found in {RANGES_DIR}")

    print(f"Repository root : {REPOSITORY_ROOT}")
    print(f"Range files     : {len(files)}")
    print()

    total_size_bytes = sum(p.stat().st_size for p in files)
    total_size_gb = total_size_bytes / (1024**3)

    inventory_rows = read_csv(INVENTORY_CSV)
    count_rows = read_csv(PRIME_COUNTS_CSV)
    runtime_rows = read_csv(RUNTIME_CSV)

    total_primes = 0
    for row in count_rows:
        for key in ("count", "prime_count", "primes", "Count"):
            if key in row:
                try:
                    total_primes += int(row[key])
                    break
                except Exception:
                    pass

    if total_primes == 0:
        # fallback from inventory if needed
        for row in inventory_rows:
            for key in ("count", "prime_count", "primes", "Count"):
                if key in row:
                    try:
                        total_primes += int(row[key])
                        break
                    except Exception:
                        pass

    runtimes = [
        parse_float(r, "runtime_min")
        for r in runtime_rows
        if r.get("status") in ("PASSED", "COMPLETE") or r.get("status")
    ]
    runtimes = [x for x in runtimes if x > 0]

    file_sizes = [(p.name, p.stat().st_size / (1024**3)) for p in files]
    largest_file = max(file_sizes, key=lambda x: x[1])
    smallest_file = min(file_sizes, key=lambda x: x[1])

    statistics_doc = {
        "repository_name": "PrimeNet Repository",
        "repository_version": REPOSITORY_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "repository_root": str(REPOSITORY_ROOT),
        "range_start": 1,
        "range_end": 1_000_000_000_000,
        "partition_count": len(files),
        "partition_size_nominal": 10_000_000_000,
        "total_size_bytes": total_size_bytes,
        "total_size_gb": total_size_gb,
        "total_primes": total_primes,
        "largest_partition": {
            "filename": largest_file[0],
            "size_gb": largest_file[1],
        },
        "smallest_partition": {
            "filename": smallest_file[0],
            "size_gb": smallest_file[1],
        },
        "python_version": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "verification_summary": str(VERIFY_SUMMARY),
        "manifest_csv": str(MANIFEST_CSV),
        "inventory_csv": str(INVENTORY_CSV),
        "prime_counts_csv": str(PRIME_COUNTS_CSV),
        "runtime_csv": str(RUNTIME_CSV),
    }

    write_json(STATISTICS_JSON, statistics_doc)
    print(f"[OK] Wrote {STATISTICS_JSON}")

    performance_doc = {
        "repository_version": REPOSITORY_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "runtime_rows": len(runtime_rows),
        "runtime_min_total_logged": sum(runtimes) if runtimes else None,
        "runtime_min_average": statistics.mean(runtimes) if runtimes else None,
        "runtime_min_median": statistics.median(runtimes) if runtimes else None,
        "runtime_min_min": min(runtimes) if runtimes else None,
        "runtime_min_max": max(runtimes) if runtimes else None,
        "runtime_min_std": statistics.stdev(runtimes) if len(runtimes) > 1 else None,
        "repository_size_gb": total_size_gb,
        "partitions": len(files),
        "average_partition_size_gb": total_size_gb / len(files),
    }

    write_json(PERFORMANCE_JSON, performance_doc)
    print(f"[OK] Wrote {PERFORMANCE_JSON}")

    print()
    print("[HASH] Computing SHA-256 hashes.")
    print("This may take several minutes for ~280 GB.")
    print()

    with HASHES_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "filename",
                "path",
                "size_bytes",
                "size_gb",
                "sha256",
                "hashed_at",
            ],
        )
        writer.writeheader()

        for i, path in enumerate(files, start=1):
            size_bytes = path.stat().st_size
            size_gb = size_bytes / (1024**3)
            print(f"[{i:03d}/{len(files):03d}] Hashing {path.name} ({size_gb:.3f} GB)")
            digest = sha256_file(path)

            writer.writerow(
                {
                    "filename": path.name,
                    "path": str(path),
                    "size_bytes": size_bytes,
                    "size_gb": f"{size_gb:.9f}",
                    "sha256": digest,
                    "hashed_at": datetime.now().isoformat(timespec="seconds"),
                }
            )

    print(f"[OK] Wrote {HASHES_CSV}")

    report = f"""PrimeNet Repository Release Report
==================================

Repository name: PrimeNet Repository
Repository version: {REPOSITORY_VERSION}
Generated at: {datetime.now().isoformat(timespec="seconds")}

Range
-----
Start: 1
End:   1,000,000,000,000

Partitions
----------
Partition count: {len(files)}
Nominal partition size: 10,000,000,000 integers

Storage
-------
Total size: {total_size_gb:.6f} GB
Largest partition:  {largest_file[0]} ({largest_file[1]:.6f} GB)
Smallest partition: {smallest_file[0]} ({smallest_file[1]:.6f} GB)

Prime Counts
------------
Total primes recorded: {total_primes:,}

Performance
-----------
Runtime rows: {len(runtime_rows)}
Average partition runtime: {performance_doc["runtime_min_average"]}

Artifacts
---------
Statistics JSON: {STATISTICS_JSON}
Performance JSON: {PERFORMANCE_JSON}
Hashes CSV: {HASHES_CSV}
Manifest CSV: {MANIFEST_CSV}
Inventory CSV: {INVENTORY_CSV}
Prime counts CSV: {PRIME_COUNTS_CSV}
Verification summary: {VERIFY_SUMMARY}

Status
------
PrimeNet Repository v1.3.0 finalization complete.
"""

    RELEASE_REPORT.write_text(report, encoding="utf-8")
    print(f"[OK] Wrote {RELEASE_REPORT}")

    print()
    print("=" * 80)
    print("PrimeNet Repository Finalization Complete")
    print("=" * 80)
    print(f"Partitions : {len(files)}")
    print(f"Size       : {total_size_gb:.6f} GB")
    print(f"Primes     : {total_primes:,}")
    print(f"Version    : {REPOSITORY_VERSION}")
    print("=" * 80)


if __name__ == "__main__":
    main()