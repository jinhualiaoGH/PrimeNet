"""
PrimeNet Repository Production Driver v2.0

Config-driven production driver.

Design:
- Big batch = monitoring unit, e.g. 100B
- Output batch = storage unit, e.g. 10B
- Avoids huge 30GB+ RAM concatenation.
- Supports --config.
- Supports skip_existing resume mode.
- Writes runtime CSV and production_status.json.

Run:

    cd C:\\PrimeNet\\Platform
    py -m core.drive_prime_repository

or:

    py -m core.drive_prime_repository --config config/repository_build.yaml
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import yaml


DEFAULT_CONFIG_PATH = Path("config/repository_build.yaml")


def fmt(n: int) -> str:
    return f"{n:,}"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError(f"Invalid config file: {path}")

    return config


def append_csv(path: Path, fieldnames: list[str], row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()

    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def write_status(path: Path, status: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, indent=2), encoding="utf-8")


def expected_output_file(repository_root: Path, start: int, end: int) -> Path:
    return repository_root / "ranges" / f"primes_{start}_{end}.npy"


def run_build_prime_range(
    start: int,
    end: int,
    overwrite: bool,
    skip_existing: bool,
) -> int:
    cmd = [
        sys.executable,
        "-m",
        "core.build_prime_range",
        "--start",
        str(start),
        "--end",
        str(end),
    ]

    if overwrite:
        cmd.append("--overwrite")

    if skip_existing:
        cmd.append("--skip-existing")

    return subprocess.run(cmd, check=False).returncode


def calculate_batches(start: int, end: int, batch_size: int) -> list[tuple[int, int]]:
    batches = []
    current = start

    while current <= end:
        batch_end = min(current + batch_size - 1, end)
        batches.append((current, batch_end))
        current = batch_end + 1

    return batches


def main() -> None:
    parser = argparse.ArgumentParser(description="PrimeNet Repository Production Driver")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to repository build YAML config file",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    config = load_config(config_path)

    repository_root = Path(config["repository"]["root"])

    range_start = int(config["range"]["start"])
    range_end = int(config["range"]["end"])

    big_batch_size = int(config["big_batch"]["size"])
    output_batch_size = int(config["output_batch"]["size"])

    overwrite = bool(config["build"]["overwrite"])
    skip_existing = bool(config["build"]["skip_existing"])

    runtime_csv = Path(config["logging"]["runtime_csv"])
    status_json = Path(config["logging"]["status_json"])

    stop_on_failure = bool(config["failure"]["stop_on_failure"])

    big_batches = calculate_batches(range_start, range_end, big_batch_size)
    output_batches = calculate_batches(range_start, range_end, output_batch_size)

    total_big_batches = len(big_batches)
    total_output_batches = len(output_batches)

    run_start_time = time.time()
    completed_output_batches = 0
    failed = False

    print("=" * 80)
    print("PrimeNet Repository Production Driver v2.0")
    print("=" * 80)
    print(f"Config          = {config_path}")
    print(f"Repository root = {repository_root}")
    print(f"Range           = {fmt(range_start)} - {fmt(range_end)}")
    print(f"Big batch size  = {fmt(big_batch_size)}")
    print(f"Output size     = {fmt(output_batch_size)}")
    print(f"Big batches     = {total_big_batches}")
    print(f"Output batches  = {total_output_batches}")
    print(f"Overwrite       = {overwrite}")
    print(f"Skip existing   = {skip_existing}")
    print(f"Runtime log     = {runtime_csv}")
    print(f"Status file     = {status_json}")
    print("=" * 80)

    for big_index, (big_start, big_end) in enumerate(big_batches, start=1):
        big_t0 = time.time()

        print()
        print("=" * 80)
        print(f"[BIG BATCH {big_index}/{total_big_batches}]")
        print(f"Range: {fmt(big_start)} - {fmt(big_end)}")
        print("=" * 80)

        sub_batches = calculate_batches(big_start, big_end, output_batch_size)

        for sub_index, (sub_start, sub_end) in enumerate(sub_batches, start=1):
            output_file = expected_output_file(repository_root, sub_start, sub_end)

            completed_output_batches += 1

            print()
            print("-" * 80)
            print(
                f"[OUTPUT BATCH {completed_output_batches}/{total_output_batches}] "
                f"BIG {big_index}.{sub_index}"
            )
            print(f"Range : {fmt(sub_start)} - {fmt(sub_end)}")
            print(f"Output: {output_file}")
            print("-" * 80)

            if skip_existing and output_file.exists():
                file_size_gb = output_file.stat().st_size / (1024**3)

                print("[SKIP] Existing output file found.")
                print(f"File size: {file_size_gb:.6f} GB")

                append_csv(
                    runtime_csv,
                    fieldnames=[
                        "timestamp",
                        "big_batch_index",
                        "total_big_batches",
                        "output_batch_index",
                        "total_output_batches",
                        "start",
                        "end",
                        "runtime_sec",
                        "runtime_min",
                        "file_exists",
                        "file_size_gb",
                        "return_code",
                        "status",
                        "elapsed_min",
                        "estimated_remaining_min",
                        "estimated_finish",
                    ],
                    row={
                        "timestamp": now_iso(),
                        "big_batch_index": big_index,
                        "total_big_batches": total_big_batches,
                        "output_batch_index": completed_output_batches,
                        "total_output_batches": total_output_batches,
                        "start": sub_start,
                        "end": sub_end,
                        "runtime_sec": "0.000",
                        "runtime_min": "0.000",
                        "file_exists": True,
                        "file_size_gb": f"{file_size_gb:.6f}",
                        "return_code": 0,
                        "status": "SKIPPED_EXISTING",
                        "elapsed_min": f"{(time.time() - run_start_time) / 60.0:.3f}",
                        "estimated_remaining_min": "",
                        "estimated_finish": "",
                    },
                )

                continue

            write_status(
                status_json,
                {
                    "timestamp": now_iso(),
                    "state": "RUNNING",
                    "big_batch_index": big_index,
                    "total_big_batches": total_big_batches,
                    "output_batch_index": completed_output_batches,
                    "total_output_batches": total_output_batches,
                    "current_start": sub_start,
                    "current_end": sub_end,
                    "output_file": str(output_file),
                },
            )

            t0 = time.time()

            return_code = run_build_prime_range(
                start=sub_start,
                end=sub_end,
                overwrite=overwrite,
                skip_existing=skip_existing,
            )

            runtime_sec = time.time() - t0
            runtime_min = runtime_sec / 60.0

            file_exists = output_file.exists()
            file_size_gb = output_file.stat().st_size / (1024**3) if file_exists else 0.0

            batch_status = "PASSED" if return_code == 0 and file_exists else "FAILED"

            elapsed_sec = time.time() - run_start_time
            avg_sec = elapsed_sec / completed_output_batches
            remaining_batches = total_output_batches - completed_output_batches
            remaining_sec = avg_sec * remaining_batches
            estimated_finish = datetime.now() + timedelta(seconds=remaining_sec)

            append_csv(
                runtime_csv,
                fieldnames=[
                    "timestamp",
                    "big_batch_index",
                    "total_big_batches",
                    "output_batch_index",
                    "total_output_batches",
                    "start",
                    "end",
                    "runtime_sec",
                    "runtime_min",
                    "file_exists",
                    "file_size_gb",
                    "return_code",
                    "status",
                    "elapsed_min",
                    "estimated_remaining_min",
                    "estimated_finish",
                ],
                row={
                    "timestamp": now_iso(),
                    "big_batch_index": big_index,
                    "total_big_batches": total_big_batches,
                    "output_batch_index": completed_output_batches,
                    "total_output_batches": total_output_batches,
                    "start": sub_start,
                    "end": sub_end,
                    "runtime_sec": f"{runtime_sec:.3f}",
                    "runtime_min": f"{runtime_min:.3f}",
                    "file_exists": file_exists,
                    "file_size_gb": f"{file_size_gb:.6f}",
                    "return_code": return_code,
                    "status": batch_status,
                    "elapsed_min": f"{elapsed_sec / 60.0:.3f}",
                    "estimated_remaining_min": f"{remaining_sec / 60.0:.3f}",
                    "estimated_finish": estimated_finish.isoformat(timespec="seconds"),
                },
            )

            write_status(
                status_json,
                {
                    "timestamp": now_iso(),
                    "state": batch_status,
                    "big_batch_index": big_index,
                    "total_big_batches": total_big_batches,
                    "output_batch_index": completed_output_batches,
                    "total_output_batches": total_output_batches,
                    "current_start": sub_start,
                    "current_end": sub_end,
                    "output_file": str(output_file),
                    "runtime_min": runtime_min,
                    "file_exists": file_exists,
                    "file_size_gb": file_size_gb,
                    "elapsed_min": elapsed_sec / 60.0,
                    "estimated_remaining_min": remaining_sec / 60.0,
                    "estimated_finish": estimated_finish.isoformat(timespec="seconds"),
                },
            )

            print()
            print("[OUTPUT BATCH SUMMARY]")
            print(f"Status        : {batch_status}")
            print(f"Runtime       : {runtime_min:.3f} min")
            print(f"File exists   : {file_exists}")
            print(f"File size     : {file_size_gb:.6f} GB")
            print(f"Completed     : {completed_output_batches}/{total_output_batches}")
            print(f"Elapsed       : {elapsed_sec / 60.0:.3f} min")
            print(f"ETA remaining : {remaining_sec / 60.0:.3f} min")
            print(f"Est. finish   : {estimated_finish.strftime('%Y-%m-%d %H:%M:%S')}")

            if batch_status != "PASSED":
                failed = True
                print("[FAILED] Output batch failed.")
                if stop_on_failure:
                    break

        big_runtime_min = (time.time() - big_t0) / 60.0

        print()
        print("=" * 80)
        print(f"[BIG BATCH {big_index} SUMMARY]")
        print(f"Range   : {fmt(big_start)} - {fmt(big_end)}")
        print(f"Runtime : {big_runtime_min:.3f} min")
        print("=" * 80)

        if failed and stop_on_failure:
            break

    final_state = "FAILED" if failed else "COMPLETE"
    total_runtime_min = (time.time() - run_start_time) / 60.0

    write_status(
        status_json,
        {
            "timestamp": now_iso(),
            "state": final_state,
            "completed_output_batches": completed_output_batches,
            "total_output_batches": total_output_batches,
            "total_runtime_min": total_runtime_min,
        },
    )

    print()
    print("=" * 80)
    print("PrimeNet Repository Production Driver v2.0 Finished")
    print("=" * 80)
    print(f"Final status : {final_state}")
    print(f"Completed    : {completed_output_batches}/{total_output_batches}")
    print(f"Runtime      : {total_runtime_min:.3f} min")
    print("=" * 80)


if __name__ == "__main__":
    main()