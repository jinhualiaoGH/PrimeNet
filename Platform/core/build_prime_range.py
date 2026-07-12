"""
PrimeNet Prime Range Builder v1.3.0
===================================

Safe, config-driven Stage 1 builder for one canonical prime range file.

Responsibilities:
    - generate one uint64 prime array;
    - write it atomically;
    - verify its structural integrity;
    - append an operational runtime record.

Non-responsibilities:
    - this module does not write repository_manifest.csv;
    - the canonical repository manifest is owned by verify_repository.py.

Example:
    py -m Platform.core.build_prime_range \
        --start 1 \
        --end 10000000000 \
        --overwrite
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from Platform.core.platform_config import (
    PlatformConfiguration,
    load_platform_config,
)


BUILDER_VERSION = "1.3.0"
DEFAULT_PROGRESS_STEP = 10

RUNTIME_FIELDS = [
    "timestamp",
    "run_id",
    "builder_version",
    "action",
    "range_start",
    "range_end",
    "segment_size",
    "progress_step",
    "output_file",
    "prime_count",
    "min_prime",
    "max_prime",
    "dtype",
    "generate_sec",
    "save_sec",
    "verify_sec",
    "total_sec",
    "total_min",
    "size_bytes",
    "size_gb",
    "status",
    "message",
]


@dataclass(frozen=True)
class BuilderPaths:
    repository_root: Path
    ranges_dir: Path
    metadata_dir: Path
    logs_dir: Path
    runtime_log: Path


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    count: int
    min_prime: int | None
    max_prime: int | None
    strictly_increasing: bool
    within_range: bool
    dtype: str


def format_int(value: int) -> str:
    return f"{value:,}"


def now_string() -> str:
    return datetime.now().isoformat(timespec="seconds")


def make_run_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{uuid.uuid4().hex[:8]}"


def resolve_paths(
    config: PlatformConfiguration,
) -> BuilderPaths:
    return BuilderPaths(
        repository_root=config.paths.repository_root,
        ranges_dir=config.paths.ranges_dir,
        metadata_dir=config.paths.metadata_dir,
        logs_dir=config.paths.logs_dir,
        runtime_log=(
            config.paths.logs_dir
            / "prime_range_runtime.csv"
        ),
    )


def ensure_directories(paths: BuilderPaths) -> None:
    paths.ranges_dir.mkdir(parents=True, exist_ok=True)
    paths.metadata_dir.mkdir(parents=True, exist_ok=True)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)


def output_path(
    paths: BuilderPaths,
    start: int,
    end: int,
) -> Path:
    return (
        paths.ranges_dir
        / f"primes_{start}_{end}.npy"
    )


def validate_parameters(
    start: int,
    end: int,
    segment_size: int,
    progress_step: int,
) -> None:
    if isinstance(start, bool) or start < 1:
        raise ValueError("start must be an integer >= 1.")

    if isinstance(end, bool) or end < start:
        raise ValueError(
            "end must be an integer >= start."
        )

    if (
        isinstance(segment_size, bool)
        or segment_size <= 0
    ):
        raise ValueError(
            "segment_size must be an integer > 0."
        )

    if (
        isinstance(progress_step, bool)
        or progress_step < 1
        or progress_step > 100
    ):
        raise ValueError(
            "progress_step must be between 1 and 100."
        )


def simple_sieve(limit: int) -> np.ndarray:
    """
    Generate all primes less than or equal to limit.
    """
    if limit < 2:
        return np.array([], dtype=np.uint64)

    sieve = np.ones(limit + 1, dtype=np.bool_)
    sieve[:2] = False

    root = math.isqrt(limit)

    for candidate in range(2, root + 1):
        if sieve[candidate]:
            sieve[
                candidate * candidate:
                limit + 1:
                candidate
            ] = False

    return np.flatnonzero(sieve).astype(
        np.uint64,
        copy=False,
    )


def segmented_primes(
    start: int,
    end: int,
    segment_size: int,
    progress_step: int,
) -> np.ndarray:
    """
    Generate all primes in the inclusive interval [start, end].
    """
    validate_parameters(
        start=start,
        end=end,
        segment_size=segment_size,
        progress_step=progress_step,
    )

    base_limit = math.isqrt(end)
    base_primes = simple_sieve(base_limit)

    total_numbers = end - start + 1
    total_segments = math.ceil(
        total_numbers / segment_size
    )

    chunks: list[np.ndarray] = []
    prime_count = 0
    next_progress = progress_step

    for segment_index, low in enumerate(
        range(start, end + 1, segment_size),
        start=1,
    ):
        high = min(
            low + segment_size - 1,
            end,
        )

        segment = np.ones(
            high - low + 1,
            dtype=np.bool_,
        )

        for prime_value in base_primes:
            prime = int(prime_value)

            if prime * prime > high:
                break

            first_multiple = max(
                prime * prime,
                ((low + prime - 1) // prime) * prime,
            )

            segment[
                first_multiple - low:
                high - low + 1:
                prime
            ] = False

        if low <= 1:
            upper = min(high, 1)

            for composite in range(low, upper + 1):
                segment[composite - low] = False

        offsets = np.flatnonzero(segment)
        chunk = (
            offsets.astype(np.uint64, copy=False)
            + np.uint64(low)
        )

        chunks.append(chunk)
        prime_count += int(chunk.size)

        progress = (
            100.0
            * segment_index
            / total_segments
        )

        if (
            progress >= next_progress
            or segment_index == total_segments
        ):
            print(
                f"[PROGRESS] {progress:6.2f}% "
                f"({segment_index}/{total_segments} segments) "
                f"current={format_int(low)}-"
                f"{format_int(high)} "
                f"primes_so_far="
                f"{format_int(prime_count)}"
            )

            while next_progress <= progress:
                next_progress += progress_step

    if not chunks:
        return np.array([], dtype=np.uint64)

    return np.concatenate(chunks)


def verify_prime_array(
    array: np.ndarray,
    start: int,
    end: int,
) -> VerificationResult:
    """
    Perform structural verification of one prime array.

    This verifies storage invariants, not a full independent
    primality proof for every element.
    """
    count = int(array.shape[0])

    if array.ndim != 1:
        return VerificationResult(
            passed=False,
            count=count,
            min_prime=None,
            max_prime=None,
            strictly_increasing=False,
            within_range=False,
            dtype=str(array.dtype),
        )

    if array.dtype != np.uint64:
        return VerificationResult(
            passed=False,
            count=count,
            min_prime=None,
            max_prime=None,
            strictly_increasing=False,
            within_range=False,
            dtype=str(array.dtype),
        )

    if count == 0:
        return VerificationResult(
            passed=True,
            count=0,
            min_prime=None,
            max_prime=None,
            strictly_increasing=True,
            within_range=True,
            dtype=str(array.dtype),
        )

    min_prime = int(array[0])
    max_prime = int(array[-1])

    strictly_increasing = bool(
        np.all(array[1:] > array[:-1])
    )
    within_range = bool(
        min_prime >= start
        and max_prime <= end
    )

    return VerificationResult(
        passed=(
            strictly_increasing
            and within_range
        ),
        count=count,
        min_prime=min_prime,
        max_prime=max_prime,
        strictly_increasing=strictly_increasing,
        within_range=within_range,
        dtype=str(array.dtype),
    )


def load_and_verify(
    path: Path,
    start: int,
    end: int,
) -> VerificationResult:
    array = np.load(
        path,
        mmap_mode="r",
        allow_pickle=False,
    )

    return verify_prime_array(
        array=array,
        start=start,
        end=end,
    )


def atomic_save_array(
    output_file: Path,
    array: np.ndarray,
) -> None:
    """
    Save an array and atomically replace the destination.
    """
    temporary_file = output_file.with_name(
        f".{output_file.name}."
        f"{uuid.uuid4().hex}.tmp.npy"
    )

    try:
        np.save(
            temporary_file,
            array,
            allow_pickle=False,
        )

        with temporary_file.open("rb") as handle:
            os.fsync(handle.fileno())

        os.replace(
            temporary_file,
            output_file,
        )
    finally:
        if temporary_file.exists():
            temporary_file.unlink()


def append_runtime_record(
    runtime_log: Path,
    row: dict[str, Any],
) -> None:
    """
    Append one operational record to prime_range_runtime.csv.

    Refuse to append if an existing header is incompatible.
    """
    runtime_log.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    exists = runtime_log.is_file()
    has_content = (
        exists
        and runtime_log.stat().st_size > 0
    )

    if has_content:
        with runtime_log.open(
            "r",
            encoding="utf-8",
            newline="",
        ) as handle:
            reader = csv.reader(handle)
            existing_header = next(reader, [])

        if existing_header != RUNTIME_FIELDS:
            raise RuntimeError(
                "Existing builder runtime log has an "
                "incompatible schema: "
                f"{runtime_log}\n"
                f"Expected: {RUNTIME_FIELDS}\n"
                f"Found:    {existing_header}"
            )

    with runtime_log.open(
        "a",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=RUNTIME_FIELDS,
            extrasaction="raise",
        )

        if not has_content:
            writer.writeheader()

        writer.writerow(row)
        handle.flush()
        os.fsync(handle.fileno())


def runtime_row(
    *,
    run_id: str,
    action: str,
    start: int,
    end: int,
    segment_size: int,
    progress_step: int,
    output_file: Path,
    verification: VerificationResult | None,
    generate_sec: float,
    save_sec: float,
    verify_sec: float,
    total_sec: float,
    size_bytes: int,
    status: str,
    message: str,
) -> dict[str, Any]:
    size_gb = (
        size_bytes / (1024 ** 3)
        if size_bytes
        else 0.0
    )

    return {
        "timestamp": now_string(),
        "run_id": run_id,
        "builder_version": BUILDER_VERSION,
        "action": action,
        "range_start": start,
        "range_end": end,
        "segment_size": segment_size,
        "progress_step": progress_step,
        "output_file": str(output_file),
        "prime_count": (
            verification.count
            if verification is not None
            else ""
        ),
        "min_prime": (
            verification.min_prime
            if verification is not None
            and verification.min_prime is not None
            else ""
        ),
        "max_prime": (
            verification.max_prime
            if verification is not None
            and verification.max_prime is not None
            else ""
        ),
        "dtype": (
            verification.dtype
            if verification is not None
            else ""
        ),
        "generate_sec": f"{generate_sec:.3f}",
        "save_sec": f"{save_sec:.3f}",
        "verify_sec": f"{verify_sec:.3f}",
        "total_sec": f"{total_sec:.3f}",
        "total_min": f"{total_sec / 60:.3f}",
        "size_bytes": size_bytes,
        "size_gb": f"{size_gb:.9f}",
        "status": status,
        "message": message,
    }


def print_header(
    *,
    run_id: str,
    paths: BuilderPaths,
    start: int,
    end: int,
    segment_size: int,
    progress_step: int,
    overwrite: bool,
    skip_existing: bool,
    dry_run: bool,
    output_file: Path,
) -> None:
    print("=" * 80)
    print(
        f"PrimeNet Prime Range Builder "
        f"v{BUILDER_VERSION}"
    )
    print("=" * 80)
    print(f"Run ID        : {run_id}")
    print(f"Range         : {format_int(start)} - {format_int(end)}")
    print(f"Segment size  : {format_int(segment_size)}")
    print(f"Progress step : {progress_step}%")
    print(f"Repository    : {paths.repository_root}")
    print(f"Output        : {output_file}")
    print(f"Runtime log   : {paths.runtime_log}")
    print(f"Overwrite     : {overwrite}")
    print(f"Skip existing : {skip_existing}")
    print(f"Dry run       : {dry_run}")
    print(
        "Canonical manifest: not written by this builder; "
        "owned by verify_repository.py"
    )
    print("=" * 80)


def build_range(
    *,
    config: PlatformConfiguration,
    start: int,
    end: int,
    segment_size: int,
    progress_step: int,
    overwrite: bool,
    skip_existing: bool,
    dry_run: bool,
) -> int:
    validate_parameters(
        start=start,
        end=end,
        segment_size=segment_size,
        progress_step=progress_step,
    )

    paths = resolve_paths(config)
    run_id = make_run_id()
    out_file = output_path(
        paths=paths,
        start=start,
        end=end,
    )

    print_header(
        run_id=run_id,
        paths=paths,
        start=start,
        end=end,
        segment_size=segment_size,
        progress_step=progress_step,
        overwrite=overwrite,
        skip_existing=skip_existing,
        dry_run=dry_run,
        output_file=out_file,
    )

    if dry_run:
        action = (
            "WOULD_OVERWRITE"
            if out_file.exists() and overwrite
            else "WOULD_INSPECT"
            if out_file.exists() and skip_existing
            else "WOULD_BUILD"
        )

        print(f"[DRY RUN] Action: {action}")
        return 0

    ensure_directories(paths)

    if out_file.exists() and not (
        overwrite or skip_existing
    ):
        print(
            "[FAILED] Existing output found. "
            "Use --overwrite or --skip-existing.",
            file=sys.stderr,
        )
        print(f"  {out_file}", file=sys.stderr)
        return 1

    total_started = time.perf_counter()

    verification: VerificationResult | None = None
    generate_sec = 0.0
    save_sec = 0.0
    verify_sec = 0.0
    action = "BUILT"
    status = "FAILED"
    message = ""
    size_bytes = 0

    try:
        if out_file.exists() and skip_existing:
            action = "INSPECTED"
            print(
                "[SKIP] Existing output retained "
                "and inspected."
            )

            verify_started = time.perf_counter()
            verification = load_and_verify(
                path=out_file,
                start=start,
                end=end,
            )
            verify_sec = (
                time.perf_counter()
                - verify_started
            )

            if not verification.passed:
                raise RuntimeError(
                    "Existing prime file failed "
                    f"structural verification: {out_file}"
                )

        else:
            if out_file.exists():
                print(
                    "[OVERWRITE] Existing output "
                    f"will be atomically replaced: {out_file}"
                )

            print("[START] Generating primes...")

            generate_started = time.perf_counter()
            primes = segmented_primes(
                start=start,
                end=end,
                segment_size=segment_size,
                progress_step=progress_step,
            )
            generate_sec = (
                time.perf_counter()
                - generate_started
            )

            print("[SAVE] Writing atomic NumPy file...")

            save_started = time.perf_counter()
            atomic_save_array(
                output_file=out_file,
                array=primes,
            )
            save_sec = (
                time.perf_counter()
                - save_started
            )

            del primes

            print(
                "[VERIFY] Reloading output "
                "read-only..."
            )

            verify_started = time.perf_counter()
            verification = load_and_verify(
                path=out_file,
                start=start,
                end=end,
            )
            verify_sec = (
                time.perf_counter()
                - verify_started
            )

            if not verification.passed:
                raise RuntimeError(
                    "Generated prime file failed "
                    f"structural verification: {out_file}"
                )

        size_bytes = out_file.stat().st_size
        status = "PASSED"

    except Exception as exc:
        message = str(exc)
        raise

    finally:
        total_sec = (
            time.perf_counter()
            - total_started
        )

        try:
            append_runtime_record(
                runtime_log=paths.runtime_log,
                row=runtime_row(
                    run_id=run_id,
                    action=action,
                    start=start,
                    end=end,
                    segment_size=segment_size,
                    progress_step=progress_step,
                    output_file=out_file,
                    verification=verification,
                    generate_sec=generate_sec,
                    save_sec=save_sec,
                    verify_sec=verify_sec,
                    total_sec=total_sec,
                    size_bytes=size_bytes,
                    status=status,
                    message=message,
                ),
            )
        except Exception as log_exc:
            if sys.exc_info()[0] is None:
                raise

            print(
                "[WARNING] Runtime logging failed "
                f"while handling another error: {log_exc}",
                file=sys.stderr,
            )

    assert verification is not None

    size_gb = size_bytes / (1024 ** 3)
    total_sec = time.perf_counter() - total_started

    print()
    print("=" * 80)
    print("Prime Range Operation Complete")
    print("=" * 80)
    print(f"Action      : {action}")
    print(f"File        : {out_file}")
    print(f"Prime count : {format_int(verification.count)}")
    print(
        "Min prime   : "
        f"{format_int(verification.min_prime)}"
        if verification.min_prime is not None
        else "Min prime   : None"
    )
    print(
        "Max prime   : "
        f"{format_int(verification.max_prime)}"
        if verification.max_prime is not None
        else "Max prime   : None"
    )
    print(f"Dtype       : {verification.dtype}")
    print(f"Size        : {size_gb:.9f} GB")
    print(f"Generate    : {generate_sec:.3f} sec")
    print(f"Save        : {save_sec:.3f} sec")
    print(f"Verify      : {verify_sec:.3f} sec")
    print(
        f"Total       : {total_sec:.3f} sec "
        f"({total_sec / 60:.3f} min)"
    )
    print(f"Status      : {status}")
    print("=" * 80)

    return 0


def parse_args() -> argparse.Namespace:
    config = load_platform_config()

    parser = argparse.ArgumentParser(
        description=(
            "Build or inspect one canonical PrimeNet "
            "uint64 prime range file."
        )
    )

    parser.add_argument(
        "--start",
        type=int,
        required=True,
        help="Inclusive numeric range start.",
    )
    parser.add_argument(
        "--end",
        type=int,
        required=True,
        help="Inclusive numeric range end.",
    )
    parser.add_argument(
        "--segment-size",
        type=int,
        default=config.campaign.segment_size,
        help=(
            "Segment size. Default from "
            "primenet_config.yaml: "
            f"{config.campaign.segment_size}"
        ),
    )
    parser.add_argument(
        "--progress-step",
        type=int,
        default=DEFAULT_PROGRESS_STEP,
        help=(
            "Progress reporting percentage, "
            "1 through 100."
        ),
    )

    mode = parser.add_mutually_exclusive_group()

    mode.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Atomically replace an existing "
            "selected output."
        ),
    )
    mode.add_argument(
        "--skip-existing",
        action="store_true",
        help=(
            "Retain and structurally inspect an "
            "existing selected output."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Print the planned action without "
            "creating or modifying files."
        ),
    )

    args = parser.parse_args()
    args.platform_config = config
    return args


def main() -> int:
    args = parse_args()

    try:
        return build_range(
            config=args.platform_config,
            start=args.start,
            end=args.end,
            segment_size=args.segment_size,
            progress_step=args.progress_step,
            overwrite=args.overwrite,
            skip_existing=args.skip_existing,
            dry_run=args.dry_run,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(f"[FAILED] {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"[FAILED] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
