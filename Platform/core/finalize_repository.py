"""
PrimeNet Repository Release Finalizer v2.0.0
============================================

Publish derived release metadata from an already certified canonical
PrimeNet prime repository.

This module does not:
    - build prime files;
    - verify prime arrays;
    - compute repository SHA-256 hashes;
    - modify canonical verification artifacts.

Authoritative input:
    repository_manifest.csv

The canonical manifest must have been produced by an accepted full run of:

    py -m Platform.core.verify_repository --mode full

Published artifacts:
    repository_statistics.json
    repository_hashes.csv
    repository_performance.json
    repository_release_report.txt

All publication artifacts are written atomically. Existing publication
artifacts are protected unless --overwrite is explicit.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import re
import statistics
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from Platform.core.platform_config import (
    PlatformConfiguration,
    load_platform_config,
)
from Platform.core.range_files import (
    RangeFile,
    sorted_range_files,
    validate_adjacency,
)


FINALIZER_NAME = "PrimeNet Repository Release Finalizer"
FINALIZER_VERSION = "2.0.0"
REPOSITORY_RELEASE_VERSION = "2.0.0"

CANONICAL_MANIFEST_FIELDS = [
    "file_name",
    "n_start",
    "n_end",
    "file_size_gb",
    "prime_count",
    "min_prime",
    "max_prime",
    "dtype",
    "sha256",
    "status",
    "messages",
    "verified_at",
    "verifier_version",
]

HASH_FIELDS = [
    "filename",
    "path",
    "range_start",
    "range_end",
    "size_bytes",
    "size_gb",
    "sha256",
    "verified_at",
    "verifier_version",
]

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class FinalizerPaths:
    repository_root: Path
    ranges_dir: Path
    metadata_dir: Path
    logs_dir: Path

    canonical_manifest: Path
    verification_summary: Path

    prime_range_runtime: Path
    repository_driver_runtime: Path

    statistics_json: Path
    hashes_csv: Path
    performance_json: Path
    release_report: Path

    @property
    def publication_outputs(self) -> tuple[Path, ...]:
        return (
            self.statistics_json,
            self.hashes_csv,
            self.performance_json,
            self.release_report,
        )


@dataclass(frozen=True)
class CertifiedPartition:
    path: Path
    range_start: int
    range_end: int
    size_bytes: int
    prime_count: int
    min_prime: int
    max_prime: int
    dtype: str
    sha256: str
    verified_at: str
    verifier_version: str

    @property
    def size_gb(self) -> float:
        return self.size_bytes / (1024 ** 3)


@dataclass(frozen=True)
class RuntimeStatistics:
    source_file: str
    source_exists: bool
    row_count: int
    accepted_row_count: int
    runtime_min_total: float | None
    runtime_min_average: float | None
    runtime_min_median: float | None
    runtime_min_minimum: float | None
    runtime_min_maximum: float | None
    runtime_min_stddev: float | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "source_exists": self.source_exists,
            "row_count": self.row_count,
            "accepted_row_count": self.accepted_row_count,
            "runtime_min_total": self.runtime_min_total,
            "runtime_min_average": self.runtime_min_average,
            "runtime_min_median": self.runtime_min_median,
            "runtime_min_minimum": self.runtime_min_minimum,
            "runtime_min_maximum": self.runtime_min_maximum,
            "runtime_min_stddev": self.runtime_min_stddev,
        }


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def make_release_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{uuid.uuid4().hex[:8]}"


def resolve_paths(
    config: PlatformConfiguration,
) -> FinalizerPaths:
    metadata = config.paths.metadata_dir
    logs = config.paths.logs_dir

    return FinalizerPaths(
        repository_root=config.paths.repository_root,
        ranges_dir=config.paths.ranges_dir,
        metadata_dir=metadata,
        logs_dir=logs,
        canonical_manifest=metadata / "repository_manifest.csv",
        verification_summary=(
            metadata / "repository_verification_summary.txt"
        ),
        prime_range_runtime=logs / "prime_range_runtime.csv",
        repository_driver_runtime=(
            logs / "repository_driver_runtime.csv"
        ),
        statistics_json=metadata / "repository_statistics.json",
        hashes_csv=metadata / "repository_hashes.csv",
        performance_json=metadata / "repository_performance.json",
        release_report=metadata / "repository_release_report.txt",
    )


def expected_ranges(
    start: int,
    end: int,
    range_size: int,
) -> list[tuple[int, int]]:
    if start < 1:
        raise ValueError("Repository extent start must be >= 1.")

    if end < start:
        raise ValueError(
            "Repository extent end must be >= repository extent start."
        )

    if range_size <= 0:
        raise ValueError("Repository range size must be > 0.")

    rows: list[tuple[int, int]] = []
    current = start

    while current <= end:
        current_end = min(
            current + range_size - 1,
            end,
        )
        rows.append((current, current_end))
        current = current_end + 1

    return rows


def require_int(
    row: dict[str, str],
    key: str,
    row_number: int,
) -> int:
    value = row.get(key)

    if value in (None, ""):
        raise ValueError(
            f"Manifest row {row_number}: missing {key!r}."
        )

    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Manifest row {row_number}: {key!r} "
            f"must be an integer, found {value!r}."
        ) from exc


def load_canonical_manifest(
    path: Path,
) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Canonical repository manifest not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        rows = list(reader)

    if header != CANONICAL_MANIFEST_FIELDS:
        raise ValueError(
            "Canonical repository manifest schema is invalid.\n"
            f"Path:     {path}\n"
            f"Expected: {CANONICAL_MANIFEST_FIELDS}\n"
            f"Found:    {header}"
        )

    return header, rows


def validate_certified_repository(
    *,
    config: PlatformConfiguration,
    paths: FinalizerPaths,
) -> list[CertifiedPartition]:
    _, rows = load_canonical_manifest(
        paths.canonical_manifest
    )

    expected = expected_ranges(
        start=config.repository_extent.start,
        end=config.repository_extent.end,
        range_size=config.campaign.range_size,
    )

    if len(rows) != len(expected):
        raise ValueError(
            "Canonical manifest row count does not match the "
            "configured repository inventory.\n"
            f"Expected: {len(expected)}\n"
            f"Found:    {len(rows)}"
        )

    physical_files = sorted_range_files(
        paths.ranges_dir,
        "primes",
    )

    if len(physical_files) != len(expected):
        raise ValueError(
            "Physical repository file count does not match the "
            "configured repository inventory.\n"
            f"Expected: {len(expected)}\n"
            f"Found:    {len(physical_files)}"
        )

    adjacency_issues = validate_adjacency(
        physical_files
    )

    if adjacency_issues:
        raise ValueError(
            "Physical repository adjacency validation failed: "
            f"{adjacency_issues[0]}"
        )

    physical_by_range = {
        (item.start, item.end): item
        for item in physical_files
    }

    certified: list[CertifiedPartition] = []
    seen_ranges: set[tuple[int, int]] = set()
    seen_names: set[str] = set()

    for row_number, (row, expected_range) in enumerate(
        zip(rows, expected),
        start=2,
    ):
        start = require_int(
            row,
            "n_start",
            row_number,
        )
        end = require_int(
            row,
            "n_end",
            row_number,
        )
        manifest_range = (start, end)

        if manifest_range != expected_range:
            raise ValueError(
                f"Manifest row {row_number}: unexpected range "
                f"{manifest_range}; expected {expected_range}."
            )

        if manifest_range in seen_ranges:
            raise ValueError(
                f"Manifest row {row_number}: duplicate range "
                f"{manifest_range}."
            )

        seen_ranges.add(manifest_range)

        filename = (row.get("file_name") or "").strip()

        if not filename:
            raise ValueError(
                f"Manifest row {row_number}: missing file_name."
            )

        if filename in seen_names:
            raise ValueError(
                f"Manifest row {row_number}: duplicate file_name "
                f"{filename!r}."
            )

        seen_names.add(filename)

        expected_filename = f"primes_{start}_{end}.npy"

        if filename != expected_filename:
            raise ValueError(
                f"Manifest row {row_number}: file_name "
                f"{filename!r} does not match expected "
                f"{expected_filename!r}."
            )

        status = (row.get("status") or "").strip().lower()

        if status != "passed":
            raise ValueError(
                f"Manifest row {row_number}: status must be "
                f"'passed', found {status!r}."
            )

        messages = (row.get("messages") or "").strip()

        if messages:
            raise ValueError(
                f"Manifest row {row_number}: passed row contains "
                f"messages: {messages!r}."
            )

        dtype = (row.get("dtype") or "").strip()

        if dtype != "uint64":
            raise ValueError(
                f"Manifest row {row_number}: dtype must be "
                f"'uint64', found {dtype!r}."
            )

        checksum = (row.get("sha256") or "").strip().lower()

        if not SHA256_RE.fullmatch(checksum):
            raise ValueError(
                f"Manifest row {row_number}: missing or invalid "
                "SHA-256 value. A successful full verification is "
                "required before finalization."
            )

        prime_count = require_int(
            row,
            "prime_count",
            row_number,
        )
        min_prime = require_int(
            row,
            "min_prime",
            row_number,
        )
        max_prime = require_int(
            row,
            "max_prime",
            row_number,
        )

        if prime_count <= 0:
            raise ValueError(
                f"Manifest row {row_number}: prime_count must be > 0."
            )

        if min_prime < max(2, start):
            raise ValueError(
                f"Manifest row {row_number}: min_prime is below "
                "the partition range."
            )

        if max_prime > end:
            raise ValueError(
                f"Manifest row {row_number}: max_prime is above "
                "the partition range."
            )

        if min_prime > max_prime:
            raise ValueError(
                f"Manifest row {row_number}: min_prime exceeds "
                "max_prime."
            )

        physical = physical_by_range.get(manifest_range)

        if physical is None:
            raise ValueError(
                f"Manifest row {row_number}: physical file is missing "
                f"for range {manifest_range}."
            )

        if physical.path.name != filename:
            raise ValueError(
                f"Manifest row {row_number}: physical filename "
                "does not match the manifest."
            )

        if not physical.path.is_file():
            raise FileNotFoundError(
                f"Certified prime file not found: {physical.path}"
            )

        size_bytes = physical.path.stat().st_size
        manifest_size_gb = float(
            row.get("file_size_gb") or "0"
        )
        physical_size_gb = size_bytes / (1024 ** 3)

        if abs(
            manifest_size_gb - physical_size_gb
        ) > 0.000001:
            raise ValueError(
                f"Manifest row {row_number}: file size differs from "
                f"the physical file. Manifest={manifest_size_gb}, "
                f"physical={physical_size_gb}."
            )

        certified.append(
            CertifiedPartition(
                path=physical.path,
                range_start=start,
                range_end=end,
                size_bytes=size_bytes,
                prime_count=prime_count,
                min_prime=min_prime,
                max_prime=max_prime,
                dtype=dtype,
                sha256=checksum,
                verified_at=(
                    row.get("verified_at") or ""
                ).strip(),
                verifier_version=(
                    row.get("verifier_version") or ""
                ).strip(),
            )
        )

    for previous, current in zip(
        certified,
        certified[1:],
    ):
        if previous.max_prime >= current.min_prime:
            raise ValueError(
                "Certified cross-file prime ordering failed: "
                f"{previous.path.name} max={previous.max_prime}, "
                f"{current.path.name} min={current.min_prime}."
            )

    return certified


def read_runtime_rows(
    path: Path,
) -> list[dict[str, str]]:
    if not path.is_file():
        return []

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


def parse_runtime_minutes(
    row: dict[str, str],
    keys: Iterable[str],
) -> float | None:
    for key in keys:
        value = row.get(key)

        if value in (None, ""):
            continue

        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue

        if parsed >= 0:
            return parsed

    return None


def runtime_statistics(
    *,
    path: Path,
    accepted_statuses: set[str],
    minute_keys: tuple[str, ...],
) -> RuntimeStatistics:
    rows = read_runtime_rows(path)
    values: list[float] = []
    accepted_rows = 0

    for row in rows:
        status = (
            row.get("status") or ""
        ).strip().upper()

        if status not in accepted_statuses:
            continue

        accepted_rows += 1

        runtime_min = parse_runtime_minutes(
            row,
            minute_keys,
        )

        if runtime_min is not None:
            values.append(runtime_min)

    return RuntimeStatistics(
        source_file=str(path),
        source_exists=path.is_file(),
        row_count=len(rows),
        accepted_row_count=accepted_rows,
        runtime_min_total=(
            sum(values)
            if values
            else None
        ),
        runtime_min_average=(
            statistics.mean(values)
            if values
            else None
        ),
        runtime_min_median=(
            statistics.median(values)
            if values
            else None
        ),
        runtime_min_minimum=(
            min(values)
            if values
            else None
        ),
        runtime_min_maximum=(
            max(values)
            if values
            else None
        ),
        runtime_min_stddev=(
            statistics.stdev(values)
            if len(values) > 1
            else None
        ),
    )


def atomic_write_text(
    path: Path,
    text: str,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_name(
        f".{path.name}.{uuid.uuid4().hex}.tmp"
    )

    try:
        with temporary.open(
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary, path)

    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    atomic_write_text(
        path,
        json.dumps(
            payload,
            indent=2,
        )
        + "\n",
    )


def atomic_write_csv(
    path: Path,
    *,
    fieldnames: list[str],
    rows: Iterable[dict[str, Any]],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_name(
        f".{path.name}.{uuid.uuid4().hex}.tmp"
    )

    try:
        with temporary.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=fieldnames,
                extrasaction="raise",
            )
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary, path)

    finally:
        if temporary.exists():
            temporary.unlink()


def ensure_output_policy(
    paths: FinalizerPaths,
    *,
    overwrite: bool,
) -> None:
    existing = [
        path
        for path in paths.publication_outputs
        if path.exists()
    ]

    if existing and not overwrite:
        listing = "\n".join(
            f"  {path}"
            for path in existing
        )
        raise FileExistsError(
            "Existing publication artifacts found. "
            "Use --overwrite to replace them atomically.\n"
            f"{listing}"
        )


def build_publication_documents(
    *,
    release_id: str,
    config: PlatformConfiguration,
    paths: FinalizerPaths,
    partitions: list[CertifiedPartition],
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, Any],
    str,
]:
    created_at = now_iso()
    total_size_bytes = sum(
        item.size_bytes
        for item in partitions
    )
    total_size_gb = (
        total_size_bytes / (1024 ** 3)
    )
    total_primes = sum(
        item.prime_count
        for item in partitions
    )

    largest = max(
        partitions,
        key=lambda item: item.size_bytes,
    )
    smallest = min(
        partitions,
        key=lambda item: item.size_bytes,
    )

    prime_runtime = runtime_statistics(
        path=paths.prime_range_runtime,
        accepted_statuses={"PASSED", "INSPECTED"},
        minute_keys=("total_min",),
    )
    driver_runtime = runtime_statistics(
        path=paths.repository_driver_runtime,
        accepted_statuses={"PASSED", "INSPECTED"},
        minute_keys=("runtime_min",),
    )

    verifier_versions = sorted(
        {
            item.verifier_version
            for item in partitions
            if item.verifier_version
        }
    )
    verification_times = sorted(
        {
            item.verified_at
            for item in partitions
            if item.verified_at
        }
    )

    statistics_doc = {
        "repository_name": "PrimeNet Repository",
        "repository_release_version": (
            REPOSITORY_RELEASE_VERSION
        ),
        "finalizer_version": FINALIZER_VERSION,
        "release_id": release_id,
        "created_at": created_at,
        "certification": {
            "manifest": str(
                paths.canonical_manifest
            ),
            "verification_summary": str(
                paths.verification_summary
            ),
            "verifier_versions": verifier_versions,
            "verification_timestamps": verification_times,
            "all_partitions_sha256_certified": True,
        },
        "repository_root": str(
            paths.repository_root
        ),
        "ranges_dir": str(paths.ranges_dir),
        "range_start": (
            config.repository_extent.start
        ),
        "range_end": (
            config.repository_extent.end
        ),
        "partition_size_nominal": (
            config.campaign.range_size
        ),
        "partition_count": len(partitions),
        "total_size_bytes": total_size_bytes,
        "total_size_gb": total_size_gb,
        "total_primes": total_primes,
        "first_prime": partitions[0].min_prime,
        "last_prime": partitions[-1].max_prime,
        "largest_partition": {
            "filename": largest.path.name,
            "size_bytes": largest.size_bytes,
            "size_gb": largest.size_gb,
        },
        "smallest_partition": {
            "filename": smallest.path.name,
            "size_bytes": smallest.size_bytes,
            "size_gb": smallest.size_gb,
        },
        "environment": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
    }

    hash_rows = [
        {
            "filename": item.path.name,
            "path": str(item.path),
            "range_start": item.range_start,
            "range_end": item.range_end,
            "size_bytes": item.size_bytes,
            "size_gb": f"{item.size_gb:.9f}",
            "sha256": item.sha256,
            "verified_at": item.verified_at,
            "verifier_version": (
                item.verifier_version
            ),
        }
        for item in partitions
    ]

    performance_doc = {
        "repository_release_version": (
            REPOSITORY_RELEASE_VERSION
        ),
        "finalizer_version": FINALIZER_VERSION,
        "release_id": release_id,
        "created_at": created_at,
        "repository_size_bytes": total_size_bytes,
        "repository_size_gb": total_size_gb,
        "partition_count": len(partitions),
        "average_partition_size_gb": (
            total_size_gb / len(partitions)
        ),
        "prime_range_builder": (
            prime_runtime.as_dict()
        ),
        "repository_driver": (
            driver_runtime.as_dict()
        ),
        "notes": [
            (
                "Performance logs are operational "
                "records and are not certification "
                "inputs."
            ),
            (
                "Missing runtime logs do not prevent "
                "release publication."
            ),
        ],
    }

    report = f"""PrimeNet Repository Release Report
==================================

Release
-------
Release ID: {release_id}
Repository release version: {REPOSITORY_RELEASE_VERSION}
Finalizer version: {FINALIZER_VERSION}
Generated at: {created_at}

Certification
-------------
Canonical manifest: {paths.canonical_manifest}
Verification summary: {paths.verification_summary}
SHA-256 certified partitions: {len(partitions)}
Verifier versions: {", ".join(verifier_versions) or "unknown"}

Repository extent
-----------------
Start: {config.repository_extent.start:,}
End:   {config.repository_extent.end:,}

Partitions
----------
Partition count: {len(partitions):,}
Nominal partition size: {config.campaign.range_size:,} integers
First partition: {partitions[0].path.name}
Last partition:  {partitions[-1].path.name}

Prime coordinates
-----------------
Total primes: {total_primes:,}
First prime:  {partitions[0].min_prime:,}
Last prime:   {partitions[-1].max_prime:,}

Storage
-------
Total size: {total_size_gb:.9f} GB
Total bytes: {total_size_bytes:,}
Largest partition:  {largest.path.name} ({largest.size_gb:.9f} GB)
Smallest partition: {smallest.path.name} ({smallest.size_gb:.9f} GB)

Publication artifacts
---------------------
Statistics JSON: {paths.statistics_json}
Performance JSON: {paths.performance_json}
Hashes CSV: {paths.hashes_csv}
Release report: {paths.release_report}

Artifact ownership
------------------
Prime builder log: {paths.prime_range_runtime}
Production driver log: {paths.repository_driver_runtime}
Canonical manifest owner: Platform.core.verify_repository
Release metadata owner: Platform.core.finalize_repository

Status
------
PrimeNet Repository release finalization complete.
All published hashes were imported from the accepted canonical
full-verification manifest; repository files were not re-hashed.
"""

    return (
        statistics_doc,
        hash_rows,
        performance_doc,
        report,
    )


def print_header(
    *,
    release_id: str,
    paths: FinalizerPaths,
    overwrite: bool,
    dry_run: bool,
) -> None:
    print("=" * 80)
    print(
        f"{FINALIZER_NAME} "
        f"v{FINALIZER_VERSION}"
    )
    print("=" * 80)
    print(f"Release ID       : {release_id}")
    print(f"Repository root  : {paths.repository_root}")
    print(f"Ranges directory : {paths.ranges_dir}")
    print(f"Canonical manifest: {paths.canonical_manifest}")
    print(f"Overwrite        : {overwrite}")
    print(f"Dry run          : {dry_run}")
    print("=" * 80)


def finalize_repository(
    *,
    config: PlatformConfiguration,
    overwrite: bool,
    dry_run: bool,
) -> int:
    paths = resolve_paths(config)
    release_id = make_release_id()

    print_header(
        release_id=release_id,
        paths=paths,
        overwrite=overwrite,
        dry_run=dry_run,
    )

    partitions = validate_certified_repository(
        config=config,
        paths=paths,
    )

    ensure_output_policy(
        paths,
        overwrite=overwrite,
    )

    (
        statistics_doc,
        hash_rows,
        performance_doc,
        report,
    ) = build_publication_documents(
        release_id=release_id,
        config=config,
        paths=paths,
        partitions=partitions,
    )

    total_size_bytes = sum(
        item.size_bytes
        for item in partitions
    )
    total_primes = sum(
        item.prime_count
        for item in partitions
    )

    print()
    print("Certified repository")
    print("-" * 80)
    print(f"Partitions : {len(partitions):,}")
    print(f"Primes     : {total_primes:,}")
    print(
        "Size       : "
        f"{total_size_bytes / (1024 ** 3):.9f} GB"
    )
    print(
        f"First file : {partitions[0].path.name}"
    )
    print(
        f"Last file  : {partitions[-1].path.name}"
    )

    print()
    print("Publication plan")
    print("-" * 80)

    for path in paths.publication_outputs:
        action = (
            "WOULD_REPLACE"
            if path.exists()
            else "WOULD_CREATE"
        )
        print(f"{action}: {path}")

    if dry_run:
        print()
        print(
            "[DRY RUN] Certification inputs were validated. "
            "No publication artifacts were modified."
        )
        return 0

    atomic_write_json(
        paths.statistics_json,
        statistics_doc,
    )
    atomic_write_csv(
        paths.hashes_csv,
        fieldnames=HASH_FIELDS,
        rows=hash_rows,
    )
    atomic_write_json(
        paths.performance_json,
        performance_doc,
    )
    atomic_write_text(
        paths.release_report,
        report,
    )

    print()
    print("=" * 80)
    print("PrimeNet Repository Release Finalization Complete")
    print("=" * 80)
    print(f"Release ID : {release_id}")
    print(f"Partitions : {len(partitions):,}")
    print(f"Primes     : {total_primes:,}")
    print(
        "Size       : "
        f"{total_size_bytes / (1024 ** 3):.9f} GB"
    )
    print(f"Statistics : {paths.statistics_json}")
    print(f"Hashes     : {paths.hashes_csv}")
    print(f"Performance: {paths.performance_json}")
    print(f"Report     : {paths.release_report}")
    print("=" * 80)

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Publish release metadata from a fully "
            "certified PrimeNet repository."
        )
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Atomically replace existing publication "
            "artifacts."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate certification inputs and print "
            "the publication plan without modifying files."
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        config = load_platform_config()

        return finalize_repository(
            config=config,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
        )

    except (
        FileExistsError,
        FileNotFoundError,
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