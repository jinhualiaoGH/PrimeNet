"""
PrimeNet Repository Production Driver v2.2.0
============================================

Safe, config-driven production driver for building the canonical
PrimeNet prime repository.

Design:
    - big batch = monitoring unit, for example 100B;
    - output batch = storage unit, for example 10B;
    - each output batch is built by Platform.core.build_prime_range;
    - existing output files may be structurally inspected and retained;
    - runtime logs use a dedicated schema;
    - production status is written atomically;
    - dry-run mode performs no repository writes.

Examples:
    py -m Platform.core.drive_prime_repository

    py -m Platform.core.drive_prime_repository \
        --config Platform/config/repository_build.yaml

    py -m Platform.core.drive_prime_repository \
        --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from Platform.core.platform_config import (
    PlatformConfiguration,
    load_platform_config,
)


DRIVER_NAME = "PrimeNet Repository Production Driver"
DRIVER_VERSION = "2.2.0"

PLATFORM_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = (
    PLATFORM_ROOT
    / "config"
    / "repository_build.yaml"
)

RUNTIME_FIELDS = [
    "timestamp",
    "run_id",
    "driver_version",
    "big_batch_index",
    "total_big_batches",
    "output_batch_index",
    "total_output_batches",
    "range_start",
    "range_end",
    "output_file",
    "runtime_sec",
    "runtime_min",
    "file_exists",
    "file_size_bytes",
    "file_size_gb",
    "return_code",
    "status",
    "elapsed_min",
    "estimated_remaining_min",
    "estimated_finish",
    "overwrite",
    "skip_existing",
    "message",
]


@dataclass(frozen=True)
class DriverPaths:
    repository_root: Path
    ranges_dir: Path
    logs_dir: Path
    runtime_csv: Path
    status_json: Path


@dataclass(frozen=True)
class DriverSettings:
    range_start: int
    range_end: int
    big_batch_size: int
    output_batch_size: int
    overwrite: bool
    skip_existing: bool
    stop_on_failure: bool


@dataclass(frozen=True)
class BatchResult:
    return_code: int
    status: str
    output_file: Path
    file_exists: bool
    file_size_bytes: int
    runtime_sec: float
    message: str


def format_int(value: int) -> str:
    return f"{value:,}"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def make_run_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{uuid.uuid4().hex[:8]}"


def load_yaml_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Repository build configuration not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        raw = yaml.safe_load(handle) or {}

    if not isinstance(raw, dict):
        raise ValueError(
            f"Repository build configuration root must be a mapping: {path}"
        )

    return raw


def require_mapping(
    raw: dict[str, Any],
    name: str,
) -> dict[str, Any]:
    value = raw.get(name)

    if not isinstance(value, dict):
        raise ValueError(
            f"Missing or invalid configuration section: {name}"
        )

    return value


def require_int(
    section: dict[str, Any],
    key: str,
    qualified_name: str,
) -> int:
    value = section.get(key)

    if value is None or isinstance(value, bool):
        raise ValueError(
            f"Configuration value {qualified_name} "
            "must be an integer."
        )

    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Configuration value {qualified_name} "
            "must be an integer."
        ) from exc


def require_bool(
    section: dict[str, Any],
    key: str,
    qualified_name: str,
) -> bool:
    value = section.get(key)

    if not isinstance(value, bool):
        raise ValueError(
            f"Configuration value {qualified_name} "
            "must be true or false."
        )

    return value


def resolve_config_path(value: str | Path) -> Path:
    path = Path(value).expanduser()

    if not path.is_absolute():
        path = PLATFORM_ROOT / path

    return path.resolve()


def resolve_log_path(
    value: str | Path,
    logs_dir: Path,
) -> Path:
    path = Path(value).expanduser()

    if not path.is_absolute():
        path = logs_dir / path

    return path.resolve()


def parse_settings(
    raw: dict[str, Any],
    platform_config: PlatformConfiguration,
) -> DriverSettings:
    range_section = require_mapping(raw, "range")
    big_batch_section = require_mapping(raw, "big_batch")
    output_batch_section = require_mapping(
        raw,
        "output_batch",
    )
    build_section = require_mapping(raw, "build")
    failure_section = require_mapping(raw, "failure")

    range_start = require_int(
        range_section,
        "start",
        "range.start",
    )
    range_end = require_int(
        range_section,
        "end",
        "range.end",
    )
    big_batch_size = require_int(
        big_batch_section,
        "size",
        "big_batch.size",
    )
    output_batch_size = require_int(
        output_batch_section,
        "size",
        "output_batch.size",
    )
    overwrite = require_bool(
        build_section,
        "overwrite",
        "build.overwrite",
    )
    skip_existing = require_bool(
        build_section,
        "skip_existing",
        "build.skip_existing",
    )
    stop_on_failure = require_bool(
        failure_section,
        "stop_on_failure",
        "failure.stop_on_failure",
    )

    extent = platform_config.repository_extent

    if range_start < extent.start:
        raise ValueError(
            "Build range starts below the canonical repository "
            f"extent: {range_start} < {extent.start}"
        )

    if range_end > extent.end:
        raise ValueError(
            "Build range ends above the canonical repository "
            f"extent: {range_end} > {extent.end}"
        )

    if range_end < range_start:
        raise ValueError(
            "Build range end must be >= build range start."
        )

    if big_batch_size <= 0:
        raise ValueError(
            "big_batch.size must be > 0."
        )

    if output_batch_size <= 0:
        raise ValueError(
            "output_batch.size must be > 0."
        )

    if big_batch_size % output_batch_size != 0:
        raise ValueError(
            "big_batch.size must be an exact multiple "
            "of output_batch.size."
        )

    if overwrite and skip_existing:
        raise ValueError(
            "build.overwrite and build.skip_existing "
            "cannot both be true."
        )

    return DriverSettings(
        range_start=range_start,
        range_end=range_end,
        big_batch_size=big_batch_size,
        output_batch_size=output_batch_size,
        overwrite=overwrite,
        skip_existing=skip_existing,
        stop_on_failure=stop_on_failure,
    )


def resolve_paths(
    raw: dict[str, Any],
    platform_config: PlatformConfiguration,
) -> DriverPaths:
    logging_section = require_mapping(raw, "logging")

    runtime_name = logging_section.get(
        "runtime_file",
        logging_section.get(
            "runtime_csv",
            "builder_runtime.csv",
        ),
    )
    status_name = logging_section.get(
        "status_file",
        logging_section.get(
            "status_json",
            "production_status.json",
        ),
    )

    if not runtime_name:
        raise ValueError(
            "logging.runtime_file must not be empty."
        )

    if not status_name:
        raise ValueError(
            "logging.status_file must not be empty."
        )

    return DriverPaths(
        repository_root=(
            platform_config.paths.repository_root
        ),
        ranges_dir=platform_config.paths.ranges_dir,
        logs_dir=platform_config.paths.logs_dir,
        runtime_csv=resolve_log_path(
            str(runtime_name),
            platform_config.paths.logs_dir,
        ),
        status_json=resolve_log_path(
            str(status_name),
            platform_config.paths.logs_dir,
        ),
    )


def calculate_batches(
    start: int,
    end: int,
    batch_size: int,
) -> list[tuple[int, int]]:
    if start < 1:
        raise ValueError(
            "Batch calculation start must be >= 1."
        )

    if end < start:
        raise ValueError(
            "Batch calculation end must be >= start."
        )

    if batch_size <= 0:
        raise ValueError(
            "Batch size must be > 0."
        )

    batches: list[tuple[int, int]] = []
    current = start

    while current <= end:
        batch_end = min(
            current + batch_size - 1,
            end,
        )
        batches.append(
            (
                current,
                batch_end,
            )
        )
        current = batch_end + 1

    return batches


def expected_output_file(
    paths: DriverPaths,
    start: int,
    end: int,
) -> Path:
    return (
        paths.ranges_dir
        / f"primes_{start}_{end}.npy"
    )


def ensure_runtime_schema(path: Path) -> bool:
    """
    Validate an existing runtime log schema.

    Returns True when the file already has content.
    """
    if not path.is_file():
        return False

    if path.stat().st_size == 0:
        return False

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.reader(handle)
        existing_header = next(reader, [])

    if existing_header != RUNTIME_FIELDS:
        raise RuntimeError(
            "Existing driver runtime log has an "
            "incompatible schema.\n"
            f"Path:     {path}\n"
            f"Expected: {RUNTIME_FIELDS}\n"
            f"Found:    {existing_header}"
        )

    return True


def append_runtime_record(
    path: Path,
    row: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    has_content = ensure_runtime_schema(path)

    with path.open(
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


def atomic_write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_name(
        f".{path.name}.{uuid.uuid4().hex}.tmp"
    )

    try:
        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                payload,
                handle,
                indent=2,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(
            temporary_path,
            path,
        )
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def build_command(
    start: int,
    end: int,
    overwrite: bool,
    skip_existing: bool,
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "Platform.core.build_prime_range",
        "--start",
        str(start),
        "--end",
        str(end),
    ]

    if overwrite:
        command.append("--overwrite")
    elif skip_existing:
        command.append("--skip-existing")

    return command


def run_build_prime_range(
    *,
    start: int,
    end: int,
    overwrite: bool,
    skip_existing: bool,
) -> int:
    command = build_command(
        start=start,
        end=end,
        overwrite=overwrite,
        skip_existing=skip_existing,
    )

    completed = subprocess.run(
        command,
        check=False,
        cwd=PLATFORM_ROOT.parent,
    )

    return int(completed.returncode)


def inspect_or_build_batch(
    *,
    paths: DriverPaths,
    start: int,
    end: int,
    overwrite: bool,
    skip_existing: bool,
) -> BatchResult:
    output_file = expected_output_file(
        paths=paths,
        start=start,
        end=end,
    )
    output_existed_before = output_file.is_file()

    started = time.perf_counter()
    message = ""

    try:
        return_code = run_build_prime_range(
            start=start,
            end=end,
            overwrite=overwrite,
            skip_existing=skip_existing,
        )
    except Exception as exc:
        return_code = 1
        message = str(exc)

    runtime_sec = time.perf_counter() - started
    file_exists = output_file.is_file()
    file_size_bytes = (
        output_file.stat().st_size
        if file_exists
        else 0
    )

    if return_code == 0 and file_exists:
        status = (
            "INSPECTED"
            if (
                skip_existing
                and not overwrite
                and output_existed_before
            )
            else "PASSED"
    )
    else:
        status = "FAILED"

        if not message:
            if return_code != 0:
                message = (
                    "Prime range builder returned "
                    f"exit code {return_code}."
                )
            elif not file_exists:
                message = (
                    "Prime range builder returned success "
                    "but the expected output file is missing."
                )

    return BatchResult(
        return_code=return_code,
        status=status,
        output_file=output_file,
        file_exists=file_exists,
        file_size_bytes=file_size_bytes,
        runtime_sec=runtime_sec,
        message=message,
    )


def runtime_record(
    *,
    run_id: str,
    settings: DriverSettings,
    big_batch_index: int,
    total_big_batches: int,
    output_batch_index: int,
    total_output_batches: int,
    start: int,
    end: int,
    result: BatchResult,
    elapsed_sec: float,
    remaining_sec: float,
    estimated_finish: datetime | None,
) -> dict[str, Any]:
    return {
        "timestamp": now_iso(),
        "run_id": run_id,
        "driver_version": DRIVER_VERSION,
        "big_batch_index": big_batch_index,
        "total_big_batches": total_big_batches,
        "output_batch_index": output_batch_index,
        "total_output_batches": total_output_batches,
        "range_start": start,
        "range_end": end,
        "output_file": str(result.output_file),
        "runtime_sec": f"{result.runtime_sec:.3f}",
        "runtime_min": (
            f"{result.runtime_sec / 60.0:.3f}"
        ),
        "file_exists": result.file_exists,
        "file_size_bytes": result.file_size_bytes,
        "file_size_gb": (
            f"{result.file_size_bytes / (1024 ** 3):.9f}"
        ),
        "return_code": result.return_code,
        "status": result.status,
        "elapsed_min": f"{elapsed_sec / 60.0:.3f}",
        "estimated_remaining_min": (
            f"{remaining_sec / 60.0:.3f}"
        ),
        "estimated_finish": (
            estimated_finish.isoformat(
                timespec="seconds",
            )
            if estimated_finish is not None
            else ""
        ),
        "overwrite": settings.overwrite,
        "skip_existing": settings.skip_existing,
        "message": result.message,
    }


def status_payload(
    *,
    run_id: str,
    state: str,
    settings: DriverSettings,
    completed_output_batches: int,
    total_output_batches: int,
    total_runtime_min: float,
    current_start: int | None = None,
    current_end: int | None = None,
    output_file: Path | None = None,
    runtime_min: float | None = None,
    file_exists: bool | None = None,
    file_size_bytes: int | None = None,
    estimated_remaining_min: float | None = None,
    estimated_finish: datetime | None = None,
    message: str = "",
) -> dict[str, Any]:
    return {
        "timestamp": now_iso(),
        "run_id": run_id,
        "driver_version": DRIVER_VERSION,
        "state": state,
        "range_start": settings.range_start,
        "range_end": settings.range_end,
        "completed_output_batches": (
            completed_output_batches
        ),
        "total_output_batches": (
            total_output_batches
        ),
        "total_runtime_min": total_runtime_min,
        "current_start": current_start,
        "current_end": current_end,
        "output_file": (
            str(output_file)
            if output_file is not None
            else None
        ),
        "runtime_min": runtime_min,
        "file_exists": file_exists,
        "file_size_bytes": file_size_bytes,
        "file_size_gb": (
            file_size_bytes / (1024 ** 3)
            if file_size_bytes is not None
            else None
        ),
        "estimated_remaining_min": (
            estimated_remaining_min
        ),
        "estimated_finish": (
            estimated_finish.isoformat(
                timespec="seconds",
            )
            if estimated_finish is not None
            else None
        ),
        "overwrite": settings.overwrite,
        "skip_existing": settings.skip_existing,
        "message": message,
    }


def print_header(
    *,
    run_id: str,
    config_path: Path,
    platform_config: PlatformConfiguration,
    paths: DriverPaths,
    settings: DriverSettings,
    total_big_batches: int,
    total_output_batches: int,
    dry_run: bool,
) -> None:
    extent = platform_config.repository_extent

    print("=" * 80)
    print(f"{DRIVER_NAME} v{DRIVER_VERSION}")
    print("=" * 80)
    print(f"Run ID          : {run_id}")
    print(f"Config          : {config_path}")
    print(f"Repository root : {paths.repository_root}")
    print(f"Ranges dir      : {paths.ranges_dir}")
    print(
        "Extent          : "
        f"{format_int(extent.start)} - "
        f"{format_int(extent.end)}"
    )
    print(
        "Range           : "
        f"{format_int(settings.range_start)} - "
        f"{format_int(settings.range_end)}"
    )
    print(
        "Big batch size  : "
        f"{format_int(settings.big_batch_size)}"
    )
    print(
        "Output size     : "
        f"{format_int(settings.output_batch_size)}"
    )
    print(f"Big batches     : {total_big_batches}")
    print(f"Output batches  : {total_output_batches}")
    print(f"Overwrite       : {settings.overwrite}")
    print(
        f"Skip existing   : "
        f"{settings.skip_existing}"
    )
    print(
        f"Stop on failure : "
        f"{settings.stop_on_failure}"
    )
    print(f"Runtime log     : {paths.runtime_csv}")
    print(f"Status file     : {paths.status_json}")
    print(f"Dry run         : {dry_run}")
    print("=" * 80)


def run_driver(
    *,
    platform_config: PlatformConfiguration,
    config_path: Path,
    raw_config: dict[str, Any],
    dry_run: bool,
) -> int:
    settings = parse_settings(
        raw=raw_config,
        platform_config=platform_config,
    )
    paths = resolve_paths(
        raw=raw_config,
        platform_config=platform_config,
    )

    big_batches = calculate_batches(
        start=settings.range_start,
        end=settings.range_end,
        batch_size=settings.big_batch_size,
    )
    output_batches = calculate_batches(
        start=settings.range_start,
        end=settings.range_end,
        batch_size=settings.output_batch_size,
    )

    total_big_batches = len(big_batches)
    total_output_batches = len(output_batches)
    run_id = make_run_id()

    print_header(
        run_id=run_id,
        config_path=config_path,
        platform_config=platform_config,
        paths=paths,
        settings=settings,
        total_big_batches=total_big_batches,
        total_output_batches=total_output_batches,
        dry_run=dry_run,
    )

    if dry_run:
        print()
        print("Planned output batches")
        print("-" * 80)

        for index, (start, end) in enumerate(
            output_batches,
            start=1,
        ):
            output_file = expected_output_file(
                paths=paths,
                start=start,
                end=end,
            )


            if output_file.exists():
                action = (
                    "WOULD_OVERWRITE"
                    if settings.overwrite
                    else "WOULD_INSPECT"
                    if settings.skip_existing
                    else "WOULD_REFUSE"
                )
            else:
                action = "WOULD_BUILD"

            print(
                f"[{index}/{total_output_batches}] "
                f"{format_int(start)} - "
                f"{format_int(end)} | "
                f"{action} | "
                f"{output_file}"
            )

        print()
        print(
            "[DRY RUN] No repository files, logs, "
            "or status files were modified."
        )
        return 0

    paths.logs_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    ensure_runtime_schema(paths.runtime_csv)

    run_started = time.perf_counter()
    completed_output_batches = 0
    attempted_output_batches = 0
    failed = False
    failure_message = ""

    atomic_write_json(
        paths.status_json,
        status_payload(
            run_id=run_id,
            state="STARTING",
            settings=settings,
            completed_output_batches=0,
            total_output_batches=total_output_batches,
            total_runtime_min=0.0,
        ),
    )

    for big_index, (big_start, big_end) in enumerate(
        big_batches,
        start=1,
    ):
        big_started = time.perf_counter()

        print()
        print("=" * 80)
        print(
            f"[BIG BATCH "
            f"{big_index}/{total_big_batches}]"
        )
        print(
            "Range: "
            f"{format_int(big_start)} - "
            f"{format_int(big_end)}"
        )
        print("=" * 80)

        sub_batches = calculate_batches(
            start=big_start,
            end=big_end,
            batch_size=settings.output_batch_size,
        )

        for sub_index, (sub_start, sub_end) in enumerate(
            sub_batches,
            start=1,
        ):
            attempted_output_batches += 1

            output_file = expected_output_file(
                paths=paths,
                start=sub_start,
                end=sub_end,
            )

            print()
            print("-" * 80)
            print(
                f"[OUTPUT BATCH "
                f"{attempted_output_batches}/"
                f"{total_output_batches}] "
                f"BIG {big_index}.{sub_index}"
            )
            print(
                "Range : "
                f"{format_int(sub_start)} - "
                f"{format_int(sub_end)}"
            )
            print(f"Output: {output_file}")
            print("-" * 80)

            elapsed_before = (
                time.perf_counter()
                - run_started
            )

            atomic_write_json(
                paths.status_json,
                status_payload(
                    run_id=run_id,
                    state="RUNNING",
                    settings=settings,
                    completed_output_batches=(
                        completed_output_batches
                    ),
                    total_output_batches=(
                        total_output_batches
                    ),
                    total_runtime_min=(
                        elapsed_before / 60.0
                    ),
                    current_start=sub_start,
                    current_end=sub_end,
                    output_file=output_file,
                ),
            )

            result = inspect_or_build_batch(
                paths=paths,
                start=sub_start,
                end=sub_end,
                overwrite=settings.overwrite,
                skip_existing=settings.skip_existing,
            )

            if result.status in {
                "PASSED",
                "INSPECTED",
            }:
                completed_output_batches += 1
            else:
                failed = True
                failure_message = result.message

            elapsed_sec = (
                time.perf_counter()
                - run_started
            )

            average_sec = (
                elapsed_sec / attempted_output_batches
            )
            remaining_batches = (
                total_output_batches
                - attempted_output_batches
            )
            remaining_sec = (
                average_sec * remaining_batches
            )
            estimated_finish = (
                datetime.now()
                + timedelta(seconds=remaining_sec)
            )

            append_runtime_record(
                paths.runtime_csv,
                runtime_record(
                    run_id=run_id,
                    settings=settings,
                    big_batch_index=big_index,
                    total_big_batches=(
                        total_big_batches
                    ),
                    output_batch_index=(
                        attempted_output_batches
                    ),
                    total_output_batches=(
                        total_output_batches
                    ),
                    start=sub_start,
                    end=sub_end,
                    result=result,
                    elapsed_sec=elapsed_sec,
                    remaining_sec=remaining_sec,
                    estimated_finish=(
                        estimated_finish
                    ),
                ),
            )

            atomic_write_json(
                paths.status_json,
                status_payload(
                    run_id=run_id,
                    state=result.status,
                    settings=settings,
                    completed_output_batches=(
                        completed_output_batches
                    ),
                    total_output_batches=(
                        total_output_batches
                    ),
                    total_runtime_min=(
                        elapsed_sec / 60.0
                    ),
                    current_start=sub_start,
                    current_end=sub_end,
                    output_file=result.output_file,
                    runtime_min=(
                        result.runtime_sec / 60.0
                    ),
                    file_exists=result.file_exists,
                    file_size_bytes=(
                        result.file_size_bytes
                    ),
                    estimated_remaining_min=(
                        remaining_sec / 60.0
                    ),
                    estimated_finish=(
                        estimated_finish
                    ),
                    message=result.message,
                ),
            )

            print()
            print("[OUTPUT BATCH SUMMARY]")
            print(f"Status        : {result.status}")
            print(
                "Runtime       : "
                f"{result.runtime_sec / 60.0:.3f} min"
            )
            print(
                f"Return code   : "
                f"{result.return_code}"
            )
            print(
                f"File exists   : "
                f"{result.file_exists}"
            )
            print(
                "File size     : "
                f"{result.file_size_bytes / (1024 ** 3):.9f} GB"
            )
            print(
                "Completed     : "
                f"{completed_output_batches}/"
                f"{total_output_batches}"
            )
            print(
                f"Elapsed       : "
                f"{elapsed_sec / 60.0:.3f} min"
            )
            print(
                "ETA remaining : "
                f"{remaining_sec / 60.0:.3f} min"
            )
            print(
                "Est. finish   : "
                f"{estimated_finish.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            if result.message:
                print(
                    f"Message       : {result.message}"
                )

            if failed:
                print(
                    "[FAILED] Output batch failed."
                )

                if settings.stop_on_failure:
                    break

        big_runtime_min = (
            time.perf_counter()
            - big_started
        ) / 60.0

        print()
        print("=" * 80)
        print(
            f"[BIG BATCH {big_index} SUMMARY]"
        )
        print(
            "Range   : "
            f"{format_int(big_start)} - "
            f"{format_int(big_end)}"
        )
        print(
            f"Runtime : {big_runtime_min:.3f} min"
        )
        print("=" * 80)

        if failed and settings.stop_on_failure:
            break

    total_runtime_min = (
        time.perf_counter()
        - run_started
    ) / 60.0

    final_state = (
        "FAILED"
        if failed
        else "COMPLETE"
    )

    atomic_write_json(
        paths.status_json,
        status_payload(
            run_id=run_id,
            state=final_state,
            settings=settings,
            completed_output_batches=(
                completed_output_batches
            ),
            total_output_batches=(
                total_output_batches
            ),
            total_runtime_min=(
                total_runtime_min
            ),
            message=failure_message,
        ),
    )

    print()
    print("=" * 80)
    print(
        f"{DRIVER_NAME} "
        f"v{DRIVER_VERSION} Finished"
    )
    print("=" * 80)
    print(f"Final status : {final_state}")
    print(
        "Completed    : "
        f"{completed_output_batches}/"
        f"{total_output_batches}"
    )
    print(
        f"Runtime      : "
        f"{total_runtime_min:.3f} min"
    )

    if failure_message:
        print(
            f"Message      : {failure_message}"
        )

    print("=" * 80)

    return 1 if failed else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=DRIVER_NAME,
    )

    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help=(
            "Path to repository build YAML "
            "configuration file."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Print the complete production plan "
            "without modifying repository files, "
            "logs, or status files."
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        platform_config = load_platform_config()
        config_path = resolve_config_path(
            args.config
        )
        raw_config = load_yaml_config(
            config_path
        )

        return run_driver(
            platform_config=platform_config,
            config_path=config_path,
            raw_config=raw_config,
            dry_run=args.dry_run,
        )

    except (
        FileNotFoundError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            f"[FAILED] {exc}",
            file=sys.stderr,
        )
        return 2

    except Exception as exc:
        print(
            f"[FAILED] {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())