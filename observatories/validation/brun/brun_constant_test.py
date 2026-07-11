"""
PrimeNet Brun Constant Observatory

VO-001: Brun Constant Validation Observatory

Computes the partial Brun sum

    sum over twin primes (p, p+2) of 1/p + 1/(p+2)

using the PrimeNet logical repository service.

This version uses the shared PrimeNetSession through PrimeNetObservatory.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import csv
import json
import re
import time
from typing import Any

import numpy as np

from core.session import PrimeNetSession
from core.observatory import PrimeNetObservatory
from core.repository import PrimeRangeFile


BRUN_CONSTANT_REFERENCE = 1.902160583104


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


def analyze_prime_file(
    path: Path,
    previous_last_prime: int | None,
) -> dict[str, Any]:
    arr = np.load(path, mmap_mode="r")

    if arr.ndim != 1:
        arr = arr.reshape(-1)

    n = int(arr.size)

    if n == 0:
        return {
            "prime_count": 0,
            "min_prime": None,
            "max_prime": None,
            "twin_pairs": 0,
            "brun_increment": 0.0,
            "new_last_prime": previous_last_prime,
        }

    first_prime = int(arr[0])
    last_prime = int(arr[-1])

    twin_pairs = 0
    brun_increment = 0.0

    # Boundary twin pair across adjacent files.
    if previous_last_prime is not None:
        if first_prime - previous_last_prime == 2:
            twin_pairs += 1
            brun_increment += (
                1.0 / float(previous_last_prime)
                + 1.0 / float(first_prime)
            )

    # Twin pairs inside file.
    diffs = arr[1:] - arr[:-1]
    mask = diffs == 2

    if np.any(mask):
        p = arr[:-1][mask].astype(np.float64)
        q = arr[1:][mask].astype(np.float64)

        twin_pairs += int(mask.sum())
        brun_increment += float(np.sum(1.0 / p + 1.0 / q))

    return {
        "prime_count": n,
        "min_prime": first_prime,
        "max_prime": last_prime,
        "twin_pairs": twin_pairs,
        "brun_increment": brun_increment,
        "new_last_prime": last_prime,
    }


class BrunConstantObservatory(PrimeNetObservatory):
    observatory_id = "VO-001"
    observatory_name = "Brun Constant Observatory"
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
        self.total_twins = 0
        self.brun_sum = 0.0
        self.global_min_prime = None
        self.global_max_prime = None

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
        previous_last_prime = None
        t0 = time.time()

        for i, record in enumerate(self.files, start=1):
            file_start = time.time()

            result = analyze_prime_file(
                path=record.file_path,
                previous_last_prime=previous_last_prime,
            )

            self.total_primes += result["prime_count"]
            self.total_twins += result["twin_pairs"]
            self.brun_sum += result["brun_increment"]

            previous_last_prime = result["new_last_prime"]

            if result["min_prime"] is not None:
                if self.global_min_prime is None:
                    self.global_min_prime = result["min_prime"]
                self.global_max_prime = result["max_prime"]

            runtime_file = time.time() - file_start
            runtime_total = time.time() - t0
            diff = BRUN_CONSTANT_REFERENCE - self.brun_sum

            self.logger.info(
                f"[{i}/{len(self.files)}] "
                f"{record.name} | "
                f"range={record.start}->{record.end} | "
                f"primes={result['prime_count']:,} | "
                f"twins={result['twin_pairs']:,} | "
                f"B_partial={self.brun_sum:.15f} | "
                f"remaining≈{diff:.15f} | "
                f"runtime={runtime_file:.2f}s"
            )

            self.checkpoint_rows.append(
                {
                    "file_index": i,
                    "range_start": record.start,
                    "range_end": record.end,
                    "file": str(record.file_path),
                    "prime_count_file": result["prime_count"],
                    "prime_count_total": self.total_primes,
                    "min_prime_file": result["min_prime"],
                    "max_prime_file": result["max_prime"],
                    "twin_pairs_file": result["twin_pairs"],
                    "twin_pairs_total": self.total_twins,
                    "brun_increment_file": result["brun_increment"],
                    "brun_sum_total": self.brun_sum,
                    "difference_from_reference": diff,
                    "runtime_sec_file": runtime_file,
                    "runtime_sec_total": runtime_total,
                }
            )

        self.metrics = {
            "source_mode": self.source_mode,
            "source_description": self.source_description,
            "prime_files_scanned": len(self.files),
            "prime_count_total": self.total_primes,
            "min_prime": self.global_min_prime,
            "max_prime": self.global_max_prime,
            "twin_prime_pairs": self.total_twins,
            "brun_partial_sum": self.brun_sum,
            "brun_reference": BRUN_CONSTANT_REFERENCE,
            "difference_reference_minus_partial": (
                BRUN_CONSTANT_REFERENCE - self.brun_sum
            ),
        }

    def validate(self) -> None:
        if self.total_primes <= 0:
            raise ValueError("Validation failed: zero primes counted.")

        if self.total_twins <= 0:
            raise ValueError("Validation failed: zero twin-prime pairs counted.")

        if self.brun_sum <= 0:
            raise ValueError("Validation failed: Brun sum is non-positive.")

        if self.brun_sum >= BRUN_CONSTANT_REFERENCE:
            self.notes = (
                "Partial Brun sum exceeded or matched the reference value. "
                "This should be checked carefully."
            )
            self.logger.warning(self.notes)
        else:
            self.notes = (
                "Partial Brun sum is positive and below the reference value, "
                "as expected for a finite repository."
            )
            self.logger.info(self.notes)

    def generate_products(self) -> None:
        fieldnames = [
            "file_index",
            "range_start",
            "range_end",
            "file",
            "prime_count_file",
            "prime_count_total",
            "min_prime_file",
            "max_prime_file",
            "twin_pairs_file",
            "twin_pairs_total",
            "brun_increment_file",
            "brun_sum_total",
            "difference_from_reference",
            "runtime_sec_file",
            "runtime_sec_total",
        ]

        csv_path = self.products_service.save_csv(
            category=self.observatory_category,
            observatory_id=self.observatory_id,
            filename="brun_constant_checkpoints.csv",
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
            filename="brun_constant_summary.json",
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
        description="PrimeNet Brun Constant Observatory."
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

    with PrimeNetSession(session_name="VO-001 Brun Constant Observatory") as session:
        obs = BrunConstantObservatory(
            session=session,
            prime_dir=args.prime_dir,
            max_files=args.max_files,
        )
        obs.run()


if __name__ == "__main__":
    main()