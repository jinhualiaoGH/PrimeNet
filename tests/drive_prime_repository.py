"""
PrimeNet Repository Driver
==========================

Build the PrimeNet prime repository batch-by-batch.

Run from:

    C:\PrimeNet\Platform

Command:

    py -m core.drive_prime_repository
"""

from __future__ import annotations

import csv
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from core.configuration import config


DRIVER_NAME = "PrimeNet Repository Driver"
DRIVER_VERSION = "1.2.0"

REPOSITORY_DIR = config.repository_root
RANGES_DIR = REPOSITORY_DIR / "ranges"
LOG_DIR = REPOSITORY_DIR / "logs"
METADATA_DIR = REPOSITORY_DIR / "metadata"

# v1.2 uses a richer runtime log. We keep the old generation_runtime.csv untouched.
BUILDER_RUNTIME_LOG = LOG_DIR / "builder_runtime.csv"
ANOMALY_LOG = LOG_DIR / "builder_anomalies.csv"
QUALITY_METRICS_JSON = METADATA_DIR / "builder_quality_metrics.json"
QUALITY_METRICS_CSV = METADATA_DIR / "builder_quality_metrics.csv"


RUNTIME_FIELDS = [
    "run_id",
    "timestamp",
    "batch_id",
    "total_batches",
    "overall_percent",
    "batch_start",
    "batch_end",
    "output_file",
    "file_size_gb",
    "runtime_seconds",
    "runtime_minutes",
    "status",
    "segment_size",
    "batch_size",
    "skip_existing",
    "overwrite_existing",
    "driver_version",
]

ANOMALY_FIELDS = [
    "run_id",
    "timestamp",
    "batch_id",
    "batch_start",
    "batch_end",
    "runtime_minutes",
    "threshold_minutes",
    "status",
    "file_size_gb",
    "severity",
    "anomaly_type",
    "note",
    "driver_version",
]

QUALITY_FIELDS = [
    "run_id",
    "timestamp",
    "driver_version",
    "repository_root",
    "repository_start",
    "repository_end",
    "batch_size",
    "segment_size",
    "expected_batches",
    "completed_batches",
    "success_batches",
    "failed_batches",
    "skipped_batches",
    "completion_percent",
    "success_rate",
    "anomaly_threshold_minutes",
    "runtime_anomalies",
    "average_runtime_minutes",
    "median_runtime_minutes",
    "min_runtime_minutes",
    "max_runtime_minutes",
    "runtime_std_minutes",
    "total_runtime_minutes",
    "total_output_size_gb",
    "average_file_size_gb",
]


def output_file(start: int, end: int) -> Path:
    return RANGES_DIR / f"primes_{start}_{end}.npy"


def append_csv(path: Path, row: dict, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not exists:
            writer.writeheader()

        writer.writerow(row)


def write_csv_replace(path: Path, row: dict, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)


def file_size_gb(path: Path) -> float:
    if not path.exists():
        return 0.0
    return path.stat().st_size / (1024**3)


def build_one_batch(start: int, end: int, overwrite: bool) -> str:
    cmd = [
        sys.executable,
        "-m",
        "core.build_prime_range",
        "--start",
        str(start),
        "--end",
        str(end),
        "--segment-size",
        str(config.segment_size),
        "--progress-step-percent",
        str(config.progress_step_percent),
    ]

    if overwrite:
        cmd.append("--overwrite")

    result = subprocess.run(cmd)

    if result.returncode == 0:
        return "success"

    return "failed"


def make_runtime_row(
    *,
    run_id: str,
    batch_id: int,
    total_batches: int,
    overall_percent: float,
    batch_start: int,
    batch_end: int,
    out_file: Path,
    size_gb: float,
    runtime_sec: float,
    status: str,
) -> dict:
    return {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "batch_id": batch_id,
        "total_batches": total_batches,
        "overall_percent": f"{overall_percent:.3f}",
        "batch_start": batch_start,
        "batch_end": batch_end,
        "output_file": str(out_file),
        "file_size_gb": f"{size_gb:.6f}",
        "runtime_seconds": f"{runtime_sec:.3f}",
        "runtime_minutes": f"{runtime_sec / 60.0:.6f}",
        "status": status,
        "segment_size": config.segment_size,
        "batch_size": config.batch_size,
        "skip_existing": config.skip_existing,
        "overwrite_existing": config.overwrite_existing,
        "driver_version": DRIVER_VERSION,
    }


def record_runtime_anomaly(
    *,
    run_id: str,
    batch_id: int,
    batch_start: int,
    batch_end: int,
    runtime_min: float,
    status: str,
    size_gb: float,
) -> None:
    if not config.save_anomaly_log:
        return

    threshold = config.anomaly_threshold_minutes
    if runtime_min < threshold:
        return

    row = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "batch_id": batch_id,
        "batch_start": batch_start,
        "batch_end": batch_end,
        "runtime_minutes": f"{runtime_min:.6f}",
        "threshold_minutes": f"{threshold:.6f}",
        "status": status,
        "file_size_gb": f"{size_gb:.6f}",
        "severity": "warning",
        "anomaly_type": "runtime_threshold_exceeded",
        "note": "Runtime exceeded configured threshold; likely environmental unless reproduced.",
        "driver_version": DRIVER_VERSION,
    }

    append_csv(ANOMALY_LOG, row, ANOMALY_FIELDS)

    print(
        f"[ANOMALY] Runtime {runtime_min:.3f} min >= "
        f"threshold {threshold:.3f} min. Recorded: {ANOMALY_LOG}"
    )


def compute_quality_metrics(run_id: str, runtime_rows: list[dict], total_driver_sec: float) -> dict:
    expected_batches = ((config.repository_end - config.repository_start) // config.batch_size) + 1

    completed_rows = [r for r in runtime_rows if r["status"] in {"success", "failed", "skipped_existing"}]
    success_rows = [r for r in runtime_rows if r["status"] == "success"]
    failed_rows = [r for r in runtime_rows if r["status"] == "failed"]
    skipped_rows = [r for r in runtime_rows if r["status"] == "skipped_existing"]

    runtime_values = [float(r["runtime_minutes"]) for r in success_rows]
    file_sizes = [float(r["file_size_gb"]) for r in success_rows if float(r["file_size_gb"]) > 0]

    if runtime_values:
        avg_runtime = statistics.mean(runtime_values)
        median_runtime = statistics.median(runtime_values)
        min_runtime = min(runtime_values)
        max_runtime = max(runtime_values)
        std_runtime = statistics.pstdev(runtime_values) if len(runtime_values) > 1 else 0.0
    else:
        avg_runtime = median_runtime = min_runtime = max_runtime = std_runtime = 0.0

    total_size = sum(file_sizes)
    avg_size = statistics.mean(file_sizes) if file_sizes else 0.0
    anomaly_count = sum(
        1 for r in success_rows if float(r["runtime_minutes"]) >= config.anomaly_threshold_minutes
    )

    completed_batches = len(completed_rows)
    success_batches = len(success_rows)
    completion_percent = (completed_batches / expected_batches) * 100.0 if expected_batches else 0.0
    success_rate = (success_batches / completed_batches) * 100.0 if completed_batches else 0.0

    return {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "driver_version": DRIVER_VERSION,
        "repository_root": str(REPOSITORY_DIR),
        "repository_start": config.repository_start,
        "repository_end": config.repository_end,
        "batch_size": config.batch_size,
        "segment_size": config.segment_size,
        "expected_batches": expected_batches,
        "completed_batches": completed_batches,
        "success_batches": success_batches,
        "failed_batches": len(failed_rows),
        "skipped_batches": len(skipped_rows),
        "completion_percent": f"{completion_percent:.3f}",
        "success_rate": f"{success_rate:.3f}",
        "anomaly_threshold_minutes": f"{config.anomaly_threshold_minutes:.6f}",
        "runtime_anomalies": anomaly_count,
        "average_runtime_minutes": f"{avg_runtime:.6f}",
        "median_runtime_minutes": f"{median_runtime:.6f}",
        "min_runtime_minutes": f"{min_runtime:.6f}",
        "max_runtime_minutes": f"{max_runtime:.6f}",
        "runtime_std_minutes": f"{std_runtime:.6f}",
        "total_runtime_minutes": f"{total_driver_sec / 60.0:.6f}",
        "total_output_size_gb": f"{total_size:.6f}",
        "average_file_size_gb": f"{avg_size:.6f}",
    }


def save_quality_metrics(metrics: dict) -> None:
    if not config.save_quality_metrics:
        return

    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    with QUALITY_METRICS_JSON.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    write_csv_replace(QUALITY_METRICS_CSV, metrics, QUALITY_FIELDS)


def print_quality_summary(metrics: dict) -> None:
    print()
    print("=" * 80)
    print("Builder Quality Metrics")
    print("=" * 80)
    print(f"Run ID:              {metrics['run_id']}")
    print(f"Completed batches:   {metrics['completed_batches']}/{metrics['expected_batches']} ({metrics['completion_percent']}%)")
    print(f"Success rate:        {metrics['success_rate']}%")
    print(f"Failed batches:      {metrics['failed_batches']}")
    print(f"Runtime anomalies:   {metrics['runtime_anomalies']} (threshold={metrics['anomaly_threshold_minutes']} min)")
    print(f"Average runtime:     {metrics['average_runtime_minutes']} min / batch")
    print(f"Median runtime:      {metrics['median_runtime_minutes']} min / batch")
    print(f"Min runtime:         {metrics['min_runtime_minutes']} min")
    print(f"Max runtime:         {metrics['max_runtime_minutes']} min")
    print(f"Runtime std dev:     {metrics['runtime_std_minutes']} min")
    print(f"Output size:         {metrics['total_output_size_gb']} GB")
    print(f"Metrics JSON:        {QUALITY_METRICS_JSON}")
    print(f"Metrics CSV:         {QUALITY_METRICS_CSV}")
    print(f"Runtime log:         {BUILDER_RUNTIME_LOG}")
    print(f"Anomaly log:         {ANOMALY_LOG}")
    print("=" * 80)


def main() -> None:
    RANGES_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    repo_start = config.repository_start
    repo_end = config.repository_end
    batch_size = config.batch_size

    total_batches = ((repo_end - repo_start) // batch_size) + 1
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 80)
    print(f"{DRIVER_NAME} v{DRIVER_VERSION}")
    print("=" * 80)
    print(f"Run ID               = {run_id}")
    print(f"Repository root      = {REPOSITORY_DIR}")
    print(f"Range start          = {repo_start:,}")
    print(f"Range end            = {repo_end:,}")
    print(f"Batch size           = {batch_size:,}")
    print(f"Segment size         = {config.segment_size:,}")
    print(f"Total batches        = {total_batches:,}")
    print(f"Skip existing        = {config.skip_existing}")
    print(f"Overwrite existing   = {config.overwrite_existing}")
    print(f"Progress step        = {config.progress_step_percent}%")
    print(f"Anomaly threshold    = {config.anomaly_threshold_minutes:.3f} min")
    print(f"Runtime log          = {BUILDER_RUNTIME_LOG}")
    print(f"Anomaly log          = {ANOMALY_LOG}")
    print("=" * 80)

    if config.skip_existing and config.overwrite_existing:
        raise ValueError(
            "Invalid configuration: skip_existing and overwrite_existing "
            "cannot both be true."
        )

    runtime_rows: list[dict] = []
    current = repo_start
    batch_id = 0
    driver_t0 = time.time()

    while current <= repo_end:
        batch_id += 1
        batch_start = current
        batch_end = min(current + batch_size - 1, repo_end)
        out_file = output_file(batch_start, batch_end)

        overall_percent_start = ((batch_id - 1) / total_batches) * 100.0
        overall_percent_end = (batch_id / total_batches) * 100.0

        print()
        print("-" * 80)
        print(
            f"[BATCH {batch_id}/{total_batches}] "
            f"overall={overall_percent_start:.1f}% -> {overall_percent_end:.1f}%"
        )
        print(f"Range:  {batch_start:,} - {batch_end:,}")
        print(f"Output: {out_file}")

        if config.skip_existing and out_file.exists():
            size_gb = file_size_gb(out_file)
            print(f"[SKIP] Existing file found: {size_gb:.6f} GB")

            row = make_runtime_row(
                run_id=run_id,
                batch_id=batch_id,
                total_batches=total_batches,
                overall_percent=overall_percent_end,
                batch_start=batch_start,
                batch_end=batch_end,
                out_file=out_file,
                size_gb=size_gb,
                runtime_sec=0.0,
                status="skipped_existing",
            )
            append_csv(BUILDER_RUNTIME_LOG, row, RUNTIME_FIELDS)
            runtime_rows.append(row)

            current = batch_end + 1
            continue

        t0 = time.time()
        status = build_one_batch(
            batch_start,
            batch_end,
            overwrite=config.overwrite_existing,
        )
        runtime_sec = time.time() - t0
        runtime_min = runtime_sec / 60.0
        size_gb = file_size_gb(out_file)

        row = make_runtime_row(
            run_id=run_id,
            batch_id=batch_id,
            total_batches=total_batches,
            overall_percent=overall_percent_end,
            batch_start=batch_start,
            batch_end=batch_end,
            out_file=out_file,
            size_gb=size_gb,
            runtime_sec=runtime_sec,
            status=status,
        )
        append_csv(BUILDER_RUNTIME_LOG, row, RUNTIME_FIELDS)
        runtime_rows.append(row)

        record_runtime_anomaly(
            run_id=run_id,
            batch_id=batch_id,
            batch_start=batch_start,
            batch_end=batch_end,
            runtime_min=runtime_min,
            status=status,
            size_gb=size_gb,
        )

        elapsed_total = time.time() - driver_t0
        avg_batch_sec = elapsed_total / batch_id
        remaining_batches = total_batches - batch_id
        eta_min = (avg_batch_sec * remaining_batches) / 60.0

        print(
            f"[BATCH DONE] status={status}, "
            f"batch_runtime={runtime_min:.3f} min, "
            f"size={size_gb:.6f} GB, "
            f"overall={overall_percent_end:.1f}%, "
            f"eta≈{eta_min:.1f} min"
        )

        if status != "success":
            print("[STOP] Batch failed. Driver stopped safely.")
            break

        current = batch_end + 1

    total_runtime = time.time() - driver_t0
    metrics = compute_quality_metrics(run_id, runtime_rows, total_runtime)
    save_quality_metrics(metrics)

    print()
    print("=" * 80)
    print("Driver finished.")
    print(f"Total runtime: {total_runtime:.3f} sec ({total_runtime / 60.0:.3f} min)")
    print("=" * 80)

    print_quality_summary(metrics)


if __name__ == "__main__":
    main()
