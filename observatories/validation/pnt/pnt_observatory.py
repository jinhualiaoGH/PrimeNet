"""
PrimeNet Prime Number Theorem Observatory

VO-002: Prime Number Theorem Validation Observatory

Validates the Prime Number Theorem using the PrimeNet logical repository.

For each prime range file, this observatory computes:

    pi(x)              = number of primes <= x
    x / log(x)         = Prime Number Theorem approximation
    absolute error     = pi(x) - x/log(x)
    relative error     = absolute error / pi(x)

It follows the standard PrimeNet observatory lifecycle:

    prepare()
    measure()
    validate()
    generate_products()
    generate_report()
    run()
"""

from __future__ import annotations

from pathlib import Path
import argparse
import math
import re
import time
from typing import Any

import numpy as np

from core.session import PrimeNetSession
from core.observatory import PrimeNetObservatory
from core.repository import PrimeRangeFile


def find_prime_files_from_directory(prime_dir: Path) -> list[PrimeRangeFile]:
    records: list[PrimeRangeFile] = []

    for path in prime_dir.rglob("*.npy"):
        nums = re.findall(r"\d+", path.stem)

        if len(nums) < 2:
            continue

        records.append(
            PrimeRangeFile(
                file_path=path,
                start=int(nums[0]),
                end=int(nums[1]),
                size_bytes=path.stat().st_size,
            )
        )

    records.sort(key=lambda r: (r.start, r.end, str(r.file_path)))
    return records


def pnt_estimate(x: int) -> float:
    if x <= 1:
        return 0.0
    return float(x) / math.log(float(x))


def analyze_prime_file(path: Path) -> dict[str, Any]:
    arr = np.load(path, mmap_mode="r")

    if arr.ndim != 1:
        arr = arr.reshape(-1)

    n = int(arr.size)

    if n == 0:
        return {
            "prime_count": 0,
            "min_prime": None,
            "max_prime": None,
        }

    return {
        "prime_count": n,
        "min_prime": int(arr[0]),
        "max_prime": int(arr[-1]),
    }


class PrimeNumberTheoremObservatory(PrimeNetObservatory):
    observatory_id = "VO-002"
    observatory_name = "Prime Number Theorem Observatory"
    observatory_category = "validation"
    observatory_version = "1.0.0"

    def __init__(
        self,
        session: PrimeNetSession | None = None,
        prime_dir: str | None = None,
        max_files: int | None = None,
    ):
        super().__init__(session=session)

        self.prime_dir = prime_dir
        self.max_files = max_files

        self.files: list[PrimeRangeFile] = []
        self.checkpoint_rows: list[dict[str, Any]] = []

        self.source_mode = ""
        self.source_description = ""

        self.total_primes = 0
        self.global_min_prime = None
        self.global_max_prime = None

        self.final_pnt_estimate = 0.0
        self.final_absolute_error = 0.0
        self.final_relative_error = 0.0

    def prepare(self) -> None:
        if self.prime_dir:
            prime_path = Path(self.prime_dir).resolve()
            self.files = find_prime_files_from_directory(prime_path)
            self.source_mode = "physical_directory"
            self.source_description = str(prime_path)
        else:
            self.files = self.repository.list_prime_files()
            self.source_mode = "logical_repository"
            self.source_description = "PrimeNet configured prime_sources"

        if self.max_files is not None:
            self.files = self.files[: self.max_files]

        if not self.files:
            raise FileNotFoundError("No prime .npy files found.")

        self.logger.info(f"Source mode       : {self.source_mode}")
        self.logger.info(f"Source description: {self.source_description}")
        self.logger.info(f"Prime files found : {len(self.files)}")

        warnings = self.repository.validate_prime_ranges(self.files)

        if warnings:
            for warning in warnings:
                self.logger.warning(warning)
        else:
            self.logger.info("Range validation  : PASSED")

    def measure(self) -> None:
        t0 = time.time()

        previous_pi_x = 0

        for i, record in enumerate(self.files, start=1):
            file_start = time.time()

            result = analyze_prime_file(record.file_path)

            self.total_primes += result["prime_count"]

            if result["min_prime"] is not None:
                if self.global_min_prime is None:
                    self.global_min_prime = result["min_prime"]
                self.global_max_prime = result["max_prime"]

            x = int(self.global_max_prime)
            pi_x = int(self.total_primes)

            estimate = pnt_estimate(x)
            absolute_error = pi_x - estimate
            relative_error = absolute_error / pi_x if pi_x else 0.0
            relative_error_abs = abs(relative_error)

            runtime_file = time.time() - file_start
            runtime_total = time.time() - t0

            monotone_ok = pi_x > previous_pi_x
            previous_pi_x = pi_x

            self.logger.info(
                f"[{i}/{len(self.files)}] "
                f"{record.name} | "
                f"x={x:,} | "
                f"pi(x)={pi_x:,} | "
                f"x/log(x)={estimate:,.3f} | "
                f"rel_error={relative_error:.8e} | "
                f"runtime={runtime_file:.2f}s"
            )

            self.checkpoint_rows.append(
                {
                    "file_index": i,
                    "range_start": record.start,
                    "range_end": record.end,
                    "file": str(record.file_path),
                    "prime_count_file": result["prime_count"],
                    "pi_x": pi_x,
                    "x": x,
                    "pnt_estimate_x_over_log_x": estimate,
                    "absolute_error_pi_minus_estimate": absolute_error,
                    "relative_error": relative_error,
                    "absolute_relative_error": relative_error_abs,
                    "monotone_pi_ok": monotone_ok,
                    "runtime_sec_file": runtime_file,
                    "runtime_sec_total": runtime_total,
                }
            )

        self.final_pnt_estimate = pnt_estimate(int(self.global_max_prime))
        self.final_absolute_error = self.total_primes - self.final_pnt_estimate
        self.final_relative_error = (
            self.final_absolute_error / self.total_primes
            if self.total_primes
            else 0.0
        )

        self.metrics = {
            "source_mode": self.source_mode,
            "source_description": self.source_description,
            "prime_files_scanned": len(self.files),
            "prime_count_total": self.total_primes,
            "min_prime": self.global_min_prime,
            "max_prime": self.global_max_prime,
            "pi_x": self.total_primes,
            "pnt_estimate_x_over_log_x": self.final_pnt_estimate,
            "absolute_error_pi_minus_estimate": self.final_absolute_error,
            "relative_error": self.final_relative_error,
            "absolute_relative_error": abs(self.final_relative_error),
        }

    def validate(self) -> None:
        if self.total_primes <= 0:
            raise ValueError("Validation failed: zero primes counted.")

        if self.global_max_prime is None or self.global_max_prime <= 1:
            raise ValueError("Validation failed: invalid maximum prime.")

        if self.final_pnt_estimate <= 0:
            raise ValueError("Validation failed: non-positive PNT estimate.")

        if abs(self.final_relative_error) >= 0.10:
            raise ValueError(
                "Validation failed: relative error is unexpectedly large."
            )

        monotone_failures = [
            row for row in self.checkpoint_rows
            if not row["monotone_pi_ok"]
        ]

        if monotone_failures:
            raise ValueError("Validation failed: pi(x) is not monotone.")

        self.notes = (
            "Prime count is monotone and the relative error against x/log(x) "
            "is within the expected validation tolerance."
        )

        self.logger.info(self.notes)

    def generate_products(self) -> None:
        fieldnames = [
            "file_index",
            "range_start",
            "range_end",
            "file",
            "prime_count_file",
            "pi_x",
            "x",
            "pnt_estimate_x_over_log_x",
            "absolute_error_pi_minus_estimate",
            "relative_error",
            "absolute_relative_error",
            "monotone_pi_ok",
            "runtime_sec_file",
            "runtime_sec_total",
        ]

        csv_path = self.products_service.save_csv(
            category=self.observatory_category,
            observatory_id=self.observatory_id,
            filename="pnt_checkpoints.csv",
            rows=self.checkpoint_rows,
            fieldnames=fieldnames,
        )

        summary = {
            "project": "PrimeNet",
            "observatory_id": self.observatory_id,
            "observatory": self.observatory_name,
            "metrics": self.metrics,
            "notes": self.notes,
            "status": "completed",
        }

        json_path = self.products_service.save_json(
            category=self.observatory_category,
            observatory_id=self.observatory_id,
            filename="pnt_summary.json",
            data=summary,
        )

        self.products["checkpoints_csv"] = str(csv_path)
        self.products["summary_json"] = str(json_path)

        manifest_path = self.products_service.save_manifest(
            category=self.observatory_category,
            observatory_id=self.observatory_id,
            products=self.products,
            metrics=self.metrics,
        )

        self.products["product_manifest"] = str(manifest_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PrimeNet Prime Number Theorem Observatory."
    )

    parser.add_argument(
        "--prime-dir",
        type=str,
        default=None,
        help=(
            "Optional physical directory containing prime .npy files. "
            "If omitted, uses PrimeNet logical repository."
        ),
    )

    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Optional limit on number of prime files for quick testing.",
    )

    args = parser.parse_args()

    with PrimeNetSession(
        session_name="VO-002 Prime Number Theorem Observatory"
    ) as session:

        obs = PrimeNumberTheoremObservatory(
            session=session,
            prime_dir=args.prime_dir,
            max_files=args.max_files,
        )

        obs.run()


if __name__ == "__main__":
    main()