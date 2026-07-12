"""
PrimeNet Direct Gap Repository Builder v3.1.0

Safe, config-driven builder for the canonical left-owned uint16 gap repository.

Safety contract:
- Importing this module performs no repository writes.
- --help prints help and exits.
- Existing outputs require explicit --overwrite or --skip-existing.
- --dry-run plans without writing.
- Gap files are written atomically.
- The canonical manifest is replaced only after a successful full run.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from Platform.core.platform_config import load_platform_config
from Platform.core.range_files import sorted_range_files


VERSION = "3.1.0"
MAX_UINT16 = int(np.iinfo(np.uint16).max)

MANIFEST_FIELDS = [
    "gap_file", "prime_file", "range_start", "range_end", "dtype",
    "prime_count", "gap_count", "min_gap", "max_gap", "first_prime",
    "last_prime", "next_prime_used", "boundary_gap",
    "terminal_next_prime_computed", "file_size_gb", "runtime_min",
    "status", "created_at",
]

RUNTIME_FIELDS = [
    "timestamp", "run_id", "batch_id", "total_batches", "range_start",
    "range_end", "runtime_sec", "runtime_min", "file_size_gb", "max_gap",
    "boundary_gap", "terminal_next_prime_computed", "action", "status",
]


@dataclass(frozen=True)
class BuilderPaths:
    repository_root: Path
    prime_dir: Path
    output_dir: Path
    metadata_dir: Path
    logs_dir: Path
    manifest_csv: Path
    runtime_csv: Path


@dataclass(frozen=True)
class BuildOptions:
    overwrite: bool
    skip_existing: bool
    dry_run: bool
    verify: bool
    start: int | None
    end: int | None


def fmt(value: int) -> str:
    return f"{value:,}"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def resolve_paths() -> BuilderPaths:
    config = load_platform_config()
    paths = config.paths
    return BuilderPaths(
        repository_root=paths.repository_root,
        prime_dir=paths.ranges_dir,
        output_dir=paths.gaps_dir,
        metadata_dir=paths.metadata_dir,
        logs_dir=paths.logs_dir,
        manifest_csv=paths.metadata_dir / "gap_build_history.csv",
        runtime_csv=paths.logs_dir / "gap_runtime.csv",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the canonical PrimeNet left-owned uint16 gap repository. "
            "Existing files are protected unless --overwrite is explicit."
        )
    )
    behavior = parser.add_mutually_exclusive_group()
    behavior.add_argument(
        "--overwrite", action="store_true",
        help="Explicitly replace existing selected gap files.",
    )
    behavior.add_argument(
        "--skip-existing", action="store_true",
        help="Keep existing selected gap files and inspect them for manifest data.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the plan without creating, modifying, or deleting files.",
    )
    parser.add_argument("--start", type=int, default=None,
                        help="Optional inclusive coordinate lower bound.")
    parser.add_argument("--end", type=int, default=None,
                        help="Optional inclusive coordinate upper bound.")
    parser.add_argument(
        "--no-verify", action="store_true",
        help="Disable post-write reload checks. Not recommended.",
    )
    args = parser.parse_args(argv)
    if args.start is not None and args.start < 1:
        parser.error("--start must be >= 1.")
    if args.end is not None and args.end < 1:
        parser.error("--end must be >= 1.")
    if args.start is not None and args.end is not None and args.start > args.end:
        parser.error("--start must be <= --end.")
    return args


def append_csv(path: Path, fieldnames: list[str], row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
        handle.flush()
        os.fsync(handle.fileno())


def write_csv_atomic(
    path: Path,
    fieldnames: list[str],
    rows: Iterable[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def is_prime_64(n: int) -> bool:
    """Deterministic Miller-Rabin primality test for n < 2**64."""
    if n < 2:
        return False
    for prime in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n == prime:
            return True
        if n % prime == 0:
            return False
    d = n - 1
    s = 0
    while d % 2 == 0:
        s += 1
        d //= 2
    for base in (2, 325, 9375, 28178, 450775, 9780504, 1795265022):
        if base % n == 0:
            continue
        x = pow(base, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def next_prime_after(n: int) -> int:
    candidate = n + 1
    if candidate <= 2:
        return 2
    if candidate % 2 == 0:
        candidate += 1
    while not is_prime_64(candidate):
        candidate += 2
    return candidate


def atomic_save_array(path: Path, array: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as handle:
            np.save(handle, array, allow_pickle=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def validate_prime_array(primes: np.ndarray, path: Path) -> None:
    if primes.ndim != 1:
        raise RuntimeError(f"Expected 1D prime array: {path}")
    if len(primes) < 2:
        raise RuntimeError(f"Too few primes in {path}")
    if primes.dtype.kind not in {"u", "i"}:
        raise RuntimeError(f"Expected integer prime dtype in {path}; got {primes.dtype}")
    if np.any(primes[1:] <= primes[:-1]):
        raise RuntimeError(f"Prime array is not strictly increasing: {path}")


def boundary_data(
    primes: np.ndarray,
    next_prime_path: Path | None,
) -> tuple[int, int, bool]:
    last_prime = int(primes[-1])
    if next_prime_path is not None:
        next_primes = np.load(next_prime_path, mmap_mode="r", allow_pickle=False)
        if next_primes.ndim != 1 or len(next_primes) == 0:
            raise RuntimeError(f"Invalid next prime partition: {next_prime_path}")
        next_prime = int(next_primes[0])
        terminal = False
    else:
        next_prime = next_prime_after(last_prime)
        terminal = True
    boundary_gap = next_prime - last_prime
    if boundary_gap <= 0:
        raise RuntimeError(
            f"Non-positive boundary gap: last={last_prime}, next={next_prime}"
        )
    if boundary_gap > MAX_UINT16:
        raise RuntimeError(f"boundary_gap={boundary_gap} exceeds uint16 capacity")
    return next_prime, boundary_gap, terminal


def build_gap_partition(
    prime_path: Path,
    next_prime_path: Path | None,
    out_path: Path,
    verify: bool,
) -> dict[str, Any]:
    primes = np.load(prime_path, mmap_mode=None, allow_pickle=False)
    validate_prime_array(primes, prime_path)
    local_diffs = primes[1:] - primes[:-1]
    max_local = int(local_diffs.max()) if len(local_diffs) else 0
    min_local = int(local_diffs.min()) if len(local_diffs) else 0
    if min_local <= 0:
        raise RuntimeError(f"Non-positive local gap found in {prime_path}")
    if max_local > MAX_UINT16:
        raise RuntimeError(
            f"max local gap={max_local} exceeds uint16 capacity in {prime_path}"
        )
    next_prime, boundary_gap, terminal = boundary_data(primes, next_prime_path)
    gaps = np.empty(len(primes), dtype=np.uint16)
    gaps[:-1] = local_diffs.astype(np.uint16, copy=False)
    gaps[-1] = np.uint16(boundary_gap)
    min_gap = int(gaps.min())
    max_gap = int(gaps.max())
    atomic_save_array(out_path, gaps)
    if verify:
        reloaded = np.load(out_path, mmap_mode="r", allow_pickle=False)
        if reloaded.ndim != 1:
            raise RuntimeError(f"Saved gap array is not 1D: {out_path}")
        if reloaded.dtype != np.uint16:
            raise RuntimeError(f"Saved gap dtype mismatch: {out_path}; got {reloaded.dtype}")
        if len(reloaded) != len(primes):
            raise RuntimeError(f"Length mismatch after save: {out_path}")
        if int(reloaded[-1]) != boundary_gap:
            raise RuntimeError(f"Boundary gap mismatch after save: {out_path}")
        if int(reloaded.min()) != min_gap or int(reloaded.max()) != max_gap:
            raise RuntimeError(f"Min/max mismatch after save: {out_path}")
    return {
        "prime_count": int(len(primes)),
        "gap_count": int(len(gaps)),
        "min_gap": min_gap,
        "max_gap": max_gap,
        "first_prime": int(primes[0]),
        "last_prime": int(primes[-1]),
        "next_prime_used": int(next_prime),
        "boundary_gap": int(boundary_gap),
        "terminal_next_prime_computed": terminal,
    }


def inspect_existing_partition(
    prime_path: Path,
    next_prime_path: Path | None,
    out_path: Path,
) -> dict[str, Any]:
    primes = np.load(prime_path, mmap_mode="r", allow_pickle=False)
    gaps = np.load(out_path, mmap_mode="r", allow_pickle=False)
    validate_prime_array(primes, prime_path)
    if gaps.ndim != 1:
        raise RuntimeError(f"Existing gap array is not 1D: {out_path}")
    if gaps.dtype != np.uint16:
        raise RuntimeError(f"Existing gap dtype mismatch: {out_path}; got {gaps.dtype}")
    if len(gaps) != len(primes):
        raise RuntimeError(
            f"Existing count mismatch: primes={len(primes)}, gaps={len(gaps)}"
        )
    next_prime, boundary_gap, terminal = boundary_data(primes, next_prime_path)
    if int(gaps[-1]) != boundary_gap:
        raise RuntimeError(f"Existing boundary gap mismatch: {out_path}")
    return {
        "prime_count": int(len(primes)),
        "gap_count": int(len(gaps)),
        "min_gap": int(gaps.min()),
        "max_gap": int(gaps.max()),
        "first_prime": int(primes[0]),
        "last_prime": int(primes[-1]),
        "next_prime_used": int(next_prime),
        "boundary_gap": int(boundary_gap),
        "terminal_next_prime_computed": terminal,
    }


def select_partitions(prime_files: list[Any], start: int | None, end: int | None) -> list[Any]:
    selected = []
    for range_file in prime_files:
        if start is not None and range_file.end < start:
            continue
        if end is not None and range_file.start > end:
            continue
        selected.append(range_file)
    return selected


def make_manifest_row(
    gap_path: Path,
    prime_path: Path,
    range_start: int,
    range_end: int,
    stats: dict[str, Any],
    runtime_min: float,
) -> dict[str, Any]:
    return {
        "gap_file": str(gap_path),
        "prime_file": str(prime_path),
        "range_start": range_start,
        "range_end": range_end,
        "dtype": "uint16",
        "prime_count": stats["prime_count"],
        "gap_count": stats["gap_count"],
        "min_gap": stats["min_gap"],
        "max_gap": stats["max_gap"],
        "first_prime": stats["first_prime"],
        "last_prime": stats["last_prime"],
        "next_prime_used": stats["next_prime_used"],
        "boundary_gap": stats["boundary_gap"],
        "terminal_next_prime_computed": stats["terminal_next_prime_computed"],
        "file_size_gb": f"{gap_path.stat().st_size / (1024**3):.9f}",
        "runtime_min": f"{runtime_min:.3f}",
        "status": "PASSED",
        "created_at": now_iso(),
    }


def preflight(paths: BuilderPaths, selected: list[Any], options: BuildOptions) -> None:
    if not paths.prime_dir.exists():
        raise RuntimeError(f"Prime directory does not exist: {paths.prime_dir}")
    if not selected:
        raise RuntimeError("No prime partitions matched the selected range.")
    if options.dry_run:
        return
    existing = [
        paths.output_dir / f"gaps_{item.start}_{item.end}.npy"
        for item in selected
        if (paths.output_dir / f"gaps_{item.start}_{item.end}.npy").exists()
    ]
    if existing and not options.overwrite and not options.skip_existing:
        sample = "\n".join(f"  {path}" for path in existing[:10])
        suffix = "" if len(existing) <= 10 else f"\n  ... and {len(existing) - 10} more"
        raise RuntimeError(
            "Existing output files found. Refusing to write without "
            "--overwrite or --skip-existing.\n" + sample + suffix
        )


def run_builder(options: BuildOptions) -> int:
    paths = resolve_paths()
    all_prime_files = sorted_range_files(paths.prime_dir, "primes")
    if not all_prime_files:
        raise RuntimeError(f"No prime files found in {paths.prime_dir}")
    selected = select_partitions(all_prime_files, options.start, options.end)
    preflight(paths, selected, options)
    full_repository_run = (
        len(selected) == len(all_prime_files)
        and selected[0].start == all_prime_files[0].start
        and selected[-1].end == all_prime_files[-1].end
    )
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    run_manifest = paths.metadata_dir / f"gap_build_manifest_{run_id}.csv"
    print("=" * 80)
    print(f"PrimeNet Direct Gap Repository Builder v{VERSION}")
    print("=" * 80)
    print("Mode          : left-owned full mode")
    print("Safety        : explicit overwrite; atomic writes")
    print(f"Run ID        : {run_id}")
    print(f"Prime files   : {len(all_prime_files)}")
    print(f"Selected      : {len(selected)}")
    print(f"Prime dir     : {paths.prime_dir}")
    print(f"Output dir    : {paths.output_dir}")
    print(f"Run manifest  : {run_manifest}")
    print(f"Canonical     : {paths.manifest_csv}")
    print(f"Runtime log   : {paths.runtime_csv}")
    print(f"Overwrite     : {options.overwrite}")
    print(f"Skip existing : {options.skip_existing}")
    print(f"Verify        : {options.verify}")
    print(f"Dry run       : {options.dry_run}")
    print("=" * 80)
    for index, range_file in enumerate(selected, start=1):
        out_path = paths.output_dir / f"gaps_{range_file.start}_{range_file.end}.npy"
        print(
            f"[PLAN {index}/{len(selected)}] "
            f"{fmt(range_file.start)} - {fmt(range_file.end)} -> {out_path}"
        )
    if options.dry_run:
        print("=" * 80)
        print("[DRY RUN COMPLETE] No files were created, modified, or deleted.")
        print("=" * 80)
        return 0
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    paths.metadata_dir.mkdir(parents=True, exist_ok=True)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, Any]] = []
    total_size_gb = 0.0
    total_t0 = time.time()
    index_by_key = {
        (item.start, item.end): position
        for position, item in enumerate(all_prime_files)
    }
    for batch_id, range_file in enumerate(selected, start=1):
        t0 = time.time()
        out_path = paths.output_dir / f"gaps_{range_file.start}_{range_file.end}.npy"
        global_index = index_by_key[(range_file.start, range_file.end)]
        next_prime_path = (
            all_prime_files[global_index + 1].path
            if global_index + 1 < len(all_prime_files) else None
        )
        print()
        print("-" * 80)
        print(f"[{batch_id}/{len(selected)}] {fmt(range_file.start)} - {fmt(range_file.end)}")
        print(f"Prime file : {range_file.path}")
        print(f"Gap file   : {out_path}")
        print("-" * 80)
        action = "BUILT"
        try:
            if out_path.exists() and options.skip_existing:
                action = "INSPECTED"
                stats = inspect_existing_partition(range_file.path, next_prime_path, out_path)
                print("[SKIP] Existing output retained and inspected.")
            else:
                stats = build_gap_partition(
                    range_file.path, next_prime_path, out_path, verify=options.verify
                )
                print("[SAVED] Atomic replacement completed.")
            runtime_sec = time.time() - t0
            runtime_min = runtime_sec / 60.0
            file_size_gb = out_path.stat().st_size / (1024**3)
            total_size_gb += file_size_gb
            row = make_manifest_row(
                out_path, range_file.path, range_file.start, range_file.end,
                stats, runtime_min,
            )
            manifest_rows.append(row)
            write_csv_atomic(run_manifest, MANIFEST_FIELDS, manifest_rows)
            append_csv(
                paths.runtime_csv,
                RUNTIME_FIELDS,
                {
                    "timestamp": now_iso(), "run_id": run_id,
                    "batch_id": batch_id, "total_batches": len(selected),
                    "range_start": range_file.start, "range_end": range_file.end,
                    "runtime_sec": f"{runtime_sec:.3f}",
                    "runtime_min": f"{runtime_min:.3f}",
                    "file_size_gb": f"{file_size_gb:.9f}",
                    "max_gap": stats["max_gap"],
                    "boundary_gap": stats["boundary_gap"],
                    "terminal_next_prime_computed": stats["terminal_next_prime_computed"],
                    "action": action, "status": "PASSED",
                },
            )
            print(f"Action    : {action}")
            print(f"Gap count : {stats['gap_count']:,}")
            print(f"Min gap   : {stats['min_gap']}")
            print(f"Max gap   : {stats['max_gap']}")
            print(f"Boundary  : {stats['boundary_gap']}")
            print(f"Terminal  : {stats['terminal_next_prime_computed']}")
            print(f"Size      : {file_size_gb:.6f} GB")
            print(f"Runtime   : {runtime_min:.3f} min")
            print("Status    : PASSED")
        except Exception as exc:
            runtime_sec = time.time() - t0
            append_csv(
                paths.runtime_csv,
                RUNTIME_FIELDS,
                {
                    "timestamp": now_iso(), "run_id": run_id,
                    "batch_id": batch_id, "total_batches": len(selected),
                    "range_start": range_file.start, "range_end": range_file.end,
                    "runtime_sec": f"{runtime_sec:.3f}",
                    "runtime_min": f"{runtime_sec / 60.0:.3f}",
                    "file_size_gb": "", "max_gap": "", "boundary_gap": "",
                    "terminal_next_prime_computed": "", "action": action,
                    "status": f"FAILED: {exc}",
                },
            )
            raise
    if full_repository_run and len(manifest_rows) == len(all_prime_files):
        write_csv_atomic(paths.manifest_csv, MANIFEST_FIELDS, manifest_rows)
        canonical_status = f"[UPDATED] {paths.manifest_csv}"
    else:
        canonical_status = "[UNCHANGED] Partial run did not replace canonical manifest."
    total_runtime_min = (time.time() - total_t0) / 60.0
    print()
    print("=" * 80)
    print("PrimeNet Direct Gap Repository Build Complete")
    print("=" * 80)
    print(f"Run ID             : {run_id}")
    print(f"Selected files     : {len(selected)}")
    print(f"Output size        : {total_size_gb:.6f} GB")
    print(f"Runtime            : {total_runtime_min:.3f} min")
    print(f"Run manifest       : {run_manifest}")
    print(f"Canonical manifest : {canonical_status}")
    print("=" * 80)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    options = BuildOptions(
        overwrite=bool(args.overwrite),
        skip_existing=bool(args.skip_existing),
        dry_run=bool(args.dry_run),
        verify=not bool(args.no_verify),
        start=args.start,
        end=args.end,
    )
    try:
        return run_builder(options)
    except KeyboardInterrupt:
        print()
        print("[INTERRUPTED] No in-progress temporary gap file was committed.")
        return 130
    except Exception as exc:
        print(f"[FAILED] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
