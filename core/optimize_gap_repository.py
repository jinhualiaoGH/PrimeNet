"""
PrimeNet Gap Repository Optimizer v1.1.0

Converts:
  E:\\PrimeNet\\Repository\\gaps\\gaps_*.npy      uint64

To:
  E:\\PrimeNet\\Repository\\gaps_u16\\gaps_*.npy  uint16

Run:
  cd C:\\PrimeNet\\Platform
  py -m core.optimize_gap_repository
"""

from __future__ import annotations

import csv
import re
import time
from datetime import datetime
from pathlib import Path

import numpy as np


ROOT = Path(r"E:\PrimeNet\Repository")
GAP_DIR = ROOT / "gaps"
OUT_DIR = ROOT / "gaps_u16"
META_DIR = ROOT / "metadata"
LOG_DIR = ROOT / "logs"

MANIFEST = META_DIR / "gap_repository_u16_manifest.csv"
RUNTIME = LOG_DIR / "gap_optimizer_runtime.csv"

OVERWRITE = True
MAX_UINT16 = np.iinfo(np.uint16).max

RE = re.compile(r"gaps_(\d+)_(\d+)\.npy$")


def fmt(n: int) -> str:
    return f"{n:,}"


def parse_name(path: Path) -> tuple[int, int]:
    m = RE.match(path.name)
    if not m:
        raise ValueError(f"Invalid gap filename: {path.name}")
    return int(m.group(1)), int(m.group(2))


def append_csv(path: Path, fieldnames: list[str], row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()

    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def main() -> None:
    print("=" * 80)
    print("PrimeNet Gap Repository Optimizer v1.1.0")
    print("=" * 80)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    files = []
    for p in GAP_DIR.glob("gaps_*.npy"):
        start, end = parse_name(p)
        files.append((start, end, p))
    files.sort(key=lambda x: x[0])

    if not files:
        raise RuntimeError(f"No gap files found in {GAP_DIR}")

    print(f"Input gap files : {len(files)}")
    print(f"Input dir       : {GAP_DIR}")
    print(f"Output dir      : {OUT_DIR}")
    print(f"Manifest        : {MANIFEST}")
    print(f"Overwrite       : {OVERWRITE}")
    print("=" * 80)

    if MANIFEST.exists():
        MANIFEST.unlink()

    total_t0 = time.time()
    total_in = 0
    total_out = 0

    for idx, (start, end, path) in enumerate(files, start=1):
        t0 = time.time()
        out = OUT_DIR / path.name

        print()
        print("-" * 80)
        print(f"[{idx}/{len(files)}] {fmt(start)} - {fmt(end)}")
        print(f"Input : {path}")
        print(f"Output: {out}")
        print("-" * 80)

        if out.exists() and not OVERWRITE:
            print("[SKIP] Existing optimized file found.")
            continue

        gaps = np.load(path, mmap_mode=None)

        max_gap = int(gaps.max()) if len(gaps) else 0
        min_gap = int(gaps.min()) if len(gaps) else 0

        if max_gap > MAX_UINT16:
            raise RuntimeError(
                f"Cannot store {path.name} as uint16; max_gap={max_gap}"
            )

        gaps_u16 = gaps.astype(np.uint16)
        np.save(out, gaps_u16)

        check = np.load(out, mmap_mode="r")
        if len(check) != len(gaps):
            raise RuntimeError(f"Length mismatch after saving {out}")
        if int(check.max()) != max_gap:
            raise RuntimeError(f"Max gap mismatch after saving {out}")

        in_size = path.stat().st_size
        out_size = out.stat().st_size
        total_in += in_size
        total_out += out_size

        runtime = time.time() - t0

        append_csv(
            MANIFEST,
            [
                "filename",
                "range_start",
                "range_end",
                "gap_count",
                "dtype",
                "min_gap",
                "max_gap",
                "input_size_gb",
                "output_size_gb",
                "compression_ratio",
                "runtime_sec",
                "status",
                "created_at",
            ],
            {
                "filename": out.name,
                "range_start": start,
                "range_end": end,
                "gap_count": len(gaps),
                "dtype": "uint16",
                "min_gap": min_gap,
                "max_gap": max_gap,
                "input_size_gb": f"{in_size / (1024**3):.9f}",
                "output_size_gb": f"{out_size / (1024**3):.9f}",
                "compression_ratio": f"{out_size / in_size:.6f}",
                "runtime_sec": f"{runtime:.3f}",
                "status": "PASSED",
                "created_at": datetime.now().isoformat(timespec="seconds"),
            },
        )

        append_csv(
            RUNTIME,
            [
                "timestamp",
                "batch_id",
                "total_batches",
                "range_start",
                "range_end",
                "runtime_sec",
                "runtime_min",
                "input_size_gb",
                "output_size_gb",
                "max_gap",
                "status",
            ],
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "batch_id": idx,
                "total_batches": len(files),
                "range_start": start,
                "range_end": end,
                "runtime_sec": f"{runtime:.3f}",
                "runtime_min": f"{runtime / 60:.3f}",
                "input_size_gb": f"{in_size / (1024**3):.9f}",
                "output_size_gb": f"{out_size / (1024**3):.9f}",
                "max_gap": max_gap,
                "status": "PASSED",
            },
        )

        print("[SAVED]")
        print(f"Gap count : {len(gaps):,}")
        print(f"Min gap   : {min_gap}")
        print(f"Max gap   : {max_gap}")
        print(f"Input     : {in_size / (1024**3):.6f} GB")
        print(f"Output    : {out_size / (1024**3):.6f} GB")
        print(f"Ratio     : {out_size / in_size:.3f}")
        print(f"Runtime   : {runtime / 60:.3f} min")
        print("Status    : PASSED")

    total_min = (time.time() - total_t0) / 60

    print()
    print("=" * 80)
    print("PrimeNet Gap Repository Optimization Complete")
    print("=" * 80)
    print(f"Files       : {len(files)}")
    print(f"Input size  : {total_in / (1024**3):.6f} GB")
    print(f"Output size : {total_out / (1024**3):.6f} GB")
    print(f"Saved       : {(total_in - total_out) / (1024**3):.6f} GB")
    print(f"Ratio       : {total_out / total_in:.6f}")
    print(f"Runtime     : {total_min:.3f} min")
    print(f"Manifest    : {MANIFEST}")
    print("=" * 80)


if __name__ == "__main__":
    main()