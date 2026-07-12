"""
PrimeNet Repository Verifier v1.3.0
===================================

Verify the canonical PrimeNet uint64 prime repository.

Verification modes
------------------
fast:
    Operational readiness verification.

    Checks:
        - exact physical file inventory;
        - canonical numeric range topology;
        - file loadability;
        - one-dimensional uint64 arrays;
        - nonempty arrays;
        - endpoint containment;
        - cross-file prime ordering.

    Skips:
        - complete within-file monotonic scanning;
        - SHA-256 hashing.

full:
    Formal repository certification.

    Performs every fast check plus:
        - chunked complete monotonic scanning;
        - SHA-256 hashing.

Artifact ownership
------------------
This module is the sole owner of:

    repository_manifest.csv
    repository_verification_summary.txt

The canonical full manifest is atomically replaced only when the entire
repository is accepted. A rejected or interrupted verification never
replaces the last accepted canonical manifest.

Fast-mode and rejected-run artifacts use separate filenames.

Examples
--------
    py -m Platform.core.verify_repository --mode fast

    py -m Platform.core.verify_repository --mode full
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from Platform.core.platform_config import (
    PlatformConfiguration,
    load_platform_config,
)
from Platform.core.range_files import (
    RangeFile,
    sorted_range_files,
    validate_adjacency,
)


VERIFIER_NAME = "PrimeNet Repository Verifier"
VERIFIER_VERSION = "1.3.0"

DEFAULT_HASH_BLOCK_SIZE = 16 * 1024 * 1024
DEFAULT_MONOTONIC_CHUNK_SIZE = 10_000_000

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

DIAGNOSTIC_MANIFEST_FIELDS = [
    "verification_mode",
    *CANONICAL_MANIFEST_FIELDS,
]


@dataclass(frozen=True)
class VerifierPaths:
    repository_root: Path
    ranges_dir: Path
    metadata_dir: Path
    canonical_manifest: Path
    canonical_summary: Path
    fast_manifest: Path
    fast_summary: Path


@dataclass(frozen=True)
class VerifierSettings:
    mode: str
    expected_start: int
    expected_end: int
    range_size: int
    segment_size: int
    hash_block_size: int
    monotonic_chunk_size: int

    @property
    def full_scan(self) -> bool:
        return self.mode == "full"

    @property
    def hashing_enabled(self) -> bool:
        return self.mode == "full"


@dataclass(frozen=True)
class FileVerification:
    range_file: RangeFile
    status: str
    messages: tuple[str, ...]
    file_size_bytes: int
    prime_count: int
    min_prime: int | None
    max_prime: int | None
    dtype: str
    sha256: str
    verified_at: str

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    def canonical_row(self) -> dict[str, Any]:
        return {
            "file_name": self.range_file.path.name,
            "n_start": self.range_file.start,
            "n_end": self.range_file.end,
            "file_size_gb": (
                f"{self.file_size_bytes / (1024 ** 3):.9f}"
            ),
            "prime_count": self.prime_count,
            "min_prime": (
                self.min_prime
                if self.min_prime is not None
                else ""
            ),
            "max_prime": (
                self.max_prime
                if self.max_prime is not None
                else ""
            ),
            "dtype": self.dtype,
            "sha256": self.sha256,
            "status": self.status,
            "messages": ";".join(self.messages),
            "verified_at": self.verified_at,
            "verifier_version": VERIFIER_VERSION,
        }

    def diagnostic_row(
        self,
        mode: str,
    ) -> dict[str, Any]:
        return {
            "verification_mode": mode,
            **self.canonical_row(),
        }


@dataclass(frozen=True)
class VerificationTotals:
    physical_files: int
    expected_files: int
    verified_files: int
    passed_files: int
    failed_files: int
    missing_ranges: int
    extra_ranges: int
    adjacency_issues: int
    boundary_issues: int

    @property
    def topology_errors(self) -> int:
        return (
            self.missing_ranges
            + self.extra_ranges
            + self.adjacency_issues
            + self.boundary_issues
        )


def now_iso() -> str:
    return datetime.now().isoformat(
        timespec="seconds"
    )


def make_run_id() -> str:
    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )
    return (
        f"{timestamp}_{uuid.uuid4().hex[:8]}"
    )


def resolve_paths(
    config: PlatformConfiguration,
) -> VerifierPaths:
    metadata_dir = config.paths.metadata_dir

    return VerifierPaths(
        repository_root=config.paths.repository_root,
        ranges_dir=config.paths.ranges_dir,
        metadata_dir=metadata_dir,
        canonical_manifest=(
            metadata_dir
            / "repository_manifest.csv"
        ),
        canonical_summary=(
            metadata_dir
            / "repository_verification_summary.txt"
        ),
        fast_manifest=(
            metadata_dir
            / "repository_fast_manifest.csv"
        ),
        fast_summary=(
            metadata_dir
            / "repository_fast_verification_summary.txt"
        ),
    )


def expected_ranges(
    start: int,
    end: int,
    range_size: int,
) -> list[tuple[int, int]]:
    if start < 1:
        raise ValueError(
            "Expected repository start must be >= 1."
        )

    if end < start:
        raise ValueError(
            "Expected repository end must be >= start."
        )

    if range_size <= 0:
        raise ValueError(
            "Expected repository range size must be > 0."
        )

    ranges: list[tuple[int, int]] = []
    current = start

    while current <= end:
        range_end = min(
            current + range_size - 1,
            end,
        )
        ranges.append(
            (
                current,
                range_end,
            )
        )
        current = range_end + 1

    return ranges


def sha256_file(
    path: Path,
    block_size: int,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            block = handle.read(block_size)

            if not block:
                break

            digest.update(block)

    return digest.hexdigest()


def chunked_strictly_increasing(
    array: np.ndarray,
    chunk_size: int,
) -> bool:
    """
    Verify strict monotonicity without allocating one enormous
    Boolean array for the complete repository block.
    """
    count = int(array.shape[0])

    if count <= 1:
        return True

    if chunk_size <= 0:
        raise ValueError(
            "Monotonic chunk size must be > 0."
        )

    previous_last = int(array[0])
    start = 1

    while start < count:
        stop = min(
            start + chunk_size,
            count,
        )

        chunk = array[start:stop]

        if chunk.size == 0:
            break

        first_value = int(chunk[0])

        if first_value <= previous_last:
            return False

        if (
            chunk.size > 1
            and not bool(
                np.all(
                    chunk[1:] > chunk[:-1]
                )
            )
        ):
            return False

        previous_last = int(chunk[-1])
        start = stop

    return True


def verify_one_file(
    range_file: RangeFile,
    settings: VerifierSettings,
) -> FileVerification:
    path = range_file.path
    messages: list[str] = []
    verified_at = now_iso()

    file_size_bytes = (
        path.stat().st_size
        if path.is_file()
        else 0
    )

    prime_count = 0
    min_prime: int | None = None
    max_prime: int | None = None
    dtype = ""
    checksum = ""

    if not path.is_file():
        return FileVerification(
            range_file=range_file,
            status="missing",
            messages=("file_missing",),
            file_size_bytes=0,
            prime_count=0,
            min_prime=None,
            max_prime=None,
            dtype="",
            sha256="",
            verified_at=verified_at,
        )

    try:
        array = np.load(
            path,
            mmap_mode="r",
            allow_pickle=False,
        )
    except Exception as exc:
        return FileVerification(
            range_file=range_file,
            status="failed",
            messages=(
                f"load_error={type(exc).__name__}: {exc}",
            ),
            file_size_bytes=file_size_bytes,
            prime_count=0,
            min_prime=None,
            max_prime=None,
            dtype="",
            sha256="",
            verified_at=verified_at,
        )

    dtype = str(array.dtype)
    prime_count = int(array.size)

    if array.ndim != 1:
        messages.append(
            f"invalid_shape={array.shape}"
        )

    if array.dtype != np.uint64:
        messages.append(
            f"invalid_dtype={array.dtype}"
        )

    if array.ndim == 1 and prime_count == 0:
        messages.append("empty_array")

    if array.ndim == 1 and prime_count > 0:
        min_prime = int(array[0])
        max_prime = int(array[-1])

        expected_minimum = max(
            2,
            range_file.start,
        )

        if min_prime < expected_minimum:
            messages.append(
                "min_prime_below_range"
            )

        if max_prime > range_file.end:
            messages.append(
                "max_prime_above_range"
            )

        if (
            settings.full_scan
            and array.dtype == np.uint64
            and not chunked_strictly_increasing(
                array=array,
                chunk_size=(
                    settings.monotonic_chunk_size
                ),
            )
        ):
            messages.append(
                "not_strictly_increasing"
            )

    if (
        settings.hashing_enabled
        and not messages
    ):
        try:
            checksum = sha256_file(
                path=path,
                block_size=settings.hash_block_size,
            )
        except Exception as exc:
            messages.append(
                "sha256_error="
                f"{type(exc).__name__}: {exc}"
            )

    status = (
        "passed"
        if not messages
        else "failed"
    )

    return FileVerification(
        range_file=range_file,
        status=status,
        messages=tuple(messages),
        file_size_bytes=file_size_bytes,
        prime_count=prime_count,
        min_prime=min_prime,
        max_prime=max_prime,
        dtype=dtype,
        sha256=checksum,
        verified_at=verified_at,
    )


def verify_boundaries(
    results: Iterable[FileVerification],
) -> list[dict[str, Any]]:
    """
    Verify strict prime ordering across adjacent repository files
    using the already collected file endpoints.
    """
    passed_results = list(results)
    issues: list[dict[str, Any]] = []

    for previous, current in zip(
        passed_results,
        passed_results[1:],
    ):
        if (
            previous.max_prime is None
            or current.min_prime is None
        ):
            issues.append(
                {
                    "issue_type": "BOUNDARY_UNAVAILABLE",
                    "previous": (
                        previous.range_file.path.name
                    ),
                    "current": (
                        current.range_file.path.name
                    ),
                    "previous_max": (
                        previous.max_prime
                    ),
                    "current_min": (
                        current.min_prime
                    ),
                }
            )
            continue

        if (
            previous.max_prime
            >= current.min_prime
        ):
            issues.append(
                {
                    "issue_type": "BOUNDARY_ORDER",
                    "previous": (
                        previous.range_file.path.name
                    ),
                    "current": (
                        current.range_file.path.name
                    ),
                    "previous_max": (
                        previous.max_prime
                    ),
                    "current_min": (
                        current.min_prime
                    ),
                }
            )

    return issues


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

    temporary_path = path.with_name(
        f".{path.name}.{uuid.uuid4().hex}.tmp"
    )

    try:
        with temporary_path.open(
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

        os.replace(
            temporary_path,
            path,
        )

    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def atomic_write_text(
    path: Path,
    text: str,
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
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(
            temporary_path,
            path,
        )

    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def atomic_write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    text = (
        json.dumps(
            payload,
            indent=2,
        )
        + "\n"
    )
    atomic_write_text(
        path=path,
        text=text,
    )


def diagnostic_manifest_path(
    metadata_dir: Path,
    *,
    mode: str,
    run_id: str,
    accepted: bool,
) -> Path:
    state = (
        "accepted"
        if accepted
        else "rejected"
    )

    return (
        metadata_dir
        / (
            f"repository_{mode}_verification_"
            f"{state}_{run_id}.csv"
        )
    )


def diagnostic_summary_path(
    metadata_dir: Path,
    *,
    mode: str,
    run_id: str,
    accepted: bool,
) -> Path:
    state = (
        "accepted"
        if accepted
        else "rejected"
    )

    return (
        metadata_dir
        / (
            f"repository_{mode}_verification_"
            f"{state}_{run_id}.txt"
        )
    )


def build_summary(
    *,
    run_id: str,
    settings: VerifierSettings,
    paths: VerifierPaths,
    totals: VerificationTotals,
    accepted: bool,
    runtime_sec: float,
    missing_ranges: list[tuple[int, int]],
    extra_ranges: list[tuple[int, int]],
    adjacency_issues: list[dict[str, Any]],
    boundary_issues: list[dict[str, Any]],
    published_manifest: Path | None,
    diagnostic_manifest: Path,
) -> str:
    lines = [
        "PrimeNet Repository Verification Summary",
        "=======================================",
        "",
        f"Run ID: {run_id}",
        f"Verified at: {now_iso()}",
        f"Verifier version: {VERIFIER_VERSION}",
        f"Verification mode: {settings.mode}",
        "",
        f"Repository root: {paths.repository_root}",
        f"Ranges directory: {paths.ranges_dir}",
        "",
        f"Configured start: {settings.expected_start}",
        f"Configured end: {settings.expected_end}",
        f"Range size: {settings.range_size}",
        f"Segment size: {settings.segment_size}",
        "",
        f"Physical files: {totals.physical_files}",
        f"Expected files: {totals.expected_files}",
        f"Verified files: {totals.verified_files}",
        f"Passed files: {totals.passed_files}",
        f"Failed files: {totals.failed_files}",
        f"Missing ranges: {totals.missing_ranges}",
        f"Extra ranges: {totals.extra_ranges}",
        f"Adjacency issues: {totals.adjacency_issues}",
        f"Boundary issues: {totals.boundary_issues}",
        f"Topology errors: {totals.topology_errors}",
        "",
        f"Full-array monotonic scan: {settings.full_scan}",
        f"SHA-256 hashing: {settings.hashing_enabled}",
        f"Monotonic chunk size: {settings.monotonic_chunk_size}",
        f"Hash block size: {settings.hash_block_size}",
        "",
        f"Accepted: {accepted}",
        f"Runtime seconds: {runtime_sec:.3f}",
        f"Runtime minutes: {runtime_sec / 60.0:.6f}",
        "",
        f"Diagnostic manifest: {diagnostic_manifest}",
        (
            f"Published canonical manifest: "
            f"{published_manifest}"
            if published_manifest is not None
            else (
                "Published canonical manifest: "
                "[UNCHANGED]"
            )
        ),
    ]

    if missing_ranges:
        lines.extend(
            [
                "",
                "Missing ranges",
                "--------------",
            ]
        )
        lines.extend(
            f"{start} - {end}"
            for start, end in missing_ranges
        )

    if extra_ranges:
        lines.extend(
            [
                "",
                "Extra ranges",
                "------------",
            ]
        )
        lines.extend(
            f"{start} - {end}"
            for start, end in extra_ranges
        )

    if adjacency_issues:
        lines.extend(
            [
                "",
                "Adjacency issues",
                "----------------",
            ]
        )
        lines.extend(
            json.dumps(
                issue,
                sort_keys=True,
            )
            for issue in adjacency_issues
        )

    if boundary_issues:
        lines.extend(
            [
                "",
                "Boundary issues",
                "---------------",
            ]
        )
        lines.extend(
            json.dumps(
                issue,
                sort_keys=True,
            )
            for issue in boundary_issues
        )

    return "\n".join(lines) + "\n"


def print_header(
    *,
    run_id: str,
    settings: VerifierSettings,
    paths: VerifierPaths,
) -> None:
    print("=" * 80)
    print(
        f"{VERIFIER_NAME} "
        f"v{VERIFIER_VERSION}"
    )
    print("=" * 80)
    print(f"Run ID            : {run_id}")
    print(f"Mode              : {settings.mode}")
    print(f"Repository root   : {paths.repository_root}")
    print(f"Ranges directory  : {paths.ranges_dir}")
    print(
        f"Expected extent   : "
        f"{settings.expected_start:,} - "
        f"{settings.expected_end:,}"
    )
    print(
        f"Range size        : "
        f"{settings.range_size:,}"
    )
    print(
        f"Full monotonicity : "
        f"{settings.full_scan}"
    )
    print(
        f"SHA-256 hashing   : "
        f"{settings.hashing_enabled}"
    )
    print(
        f"Canonical manifest: "
        f"{paths.canonical_manifest}"
    )
    print("=" * 80)


def run_verification(
    *,
    config: PlatformConfiguration,
    settings: VerifierSettings,
) -> int:
    paths = resolve_paths(config)
    run_id = make_run_id()
    started = time.perf_counter()

    print_header(
        run_id=run_id,
        settings=settings,
        paths=paths,
    )

    if not paths.ranges_dir.is_dir():
        raise FileNotFoundError(
            f"Ranges directory not found: "
            f"{paths.ranges_dir}"
        )

    expected = expected_ranges(
        start=settings.expected_start,
        end=settings.expected_end,
        range_size=settings.range_size,
    )
    expected_keys = set(expected)

    physical_files = sorted_range_files(
        paths.ranges_dir,
        "primes",
    )
    physical_keys = {
        (
            range_file.start,
            range_file.end,
        )
        for range_file in physical_files
    }

    missing_ranges = sorted(
        expected_keys - physical_keys
    )
    extra_ranges = sorted(
        physical_keys - expected_keys
    )

    expected_inventory = [
        RangeFile(
            path=(
                paths.ranges_dir
                / f"primes_{start}_{end}.npy"
            ),
            kind="primes",
            start=start,
            end=end,
        )
        for start, end in expected
    ]

    adjacency_issues = validate_adjacency(
        physical_files
    )

    print()
    print("Repository topology")
    print("-" * 80)
    print(
        f"Physical files  : "
        f"{len(physical_files)}"
    )
    print(
        f"Expected files  : "
        f"{len(expected_inventory)}"
    )
    print(
        f"Missing ranges  : "
        f"{len(missing_ranges)}"
    )
    print(
        f"Extra ranges    : "
        f"{len(extra_ranges)}"
    )
    print(
        f"Adjacency issues: "
        f"{len(adjacency_issues)}"
    )

    results: list[FileVerification] = []

    for index, range_file in enumerate(
        expected_inventory,
        start=1,
    ):
        print()
        print("-" * 80)
        print(
            f"[{index}/{len(expected_inventory)}] "
            f"{range_file.start:,} - "
            f"{range_file.end:,}"
        )

        result = verify_one_file(
            range_file=range_file,
            settings=settings,
        )
        results.append(result)

        if result.passed:
            print(
                "[PASSED] "
                f"count={result.prime_count:,}, "
                f"min={result.min_prime}, "
                f"max={result.max_prime}, "
                f"size="
                f"{result.file_size_bytes / (1024 ** 3):.9f} GB"
            )
        else:
            print(
                f"[{result.status.upper()}] "
                f"{';'.join(result.messages)}"
            )

    boundary_issues = verify_boundaries(
        results
    )

    passed_files = sum(
        result.passed
        for result in results
    )
    failed_files = sum(
        result.status == "failed"
        for result in results
    )
    missing_files = sum(
        result.status == "missing"
        for result in results
    )

    totals = VerificationTotals(
        physical_files=len(physical_files),
        expected_files=len(expected_inventory),
        verified_files=len(results),
        passed_files=passed_files,
        failed_files=(
            failed_files + missing_files
        ),
        missing_ranges=len(missing_ranges),
        extra_ranges=len(extra_ranges),
        adjacency_issues=len(adjacency_issues),
        boundary_issues=len(boundary_issues),
    )

    accepted = (
        totals.physical_files
        == totals.expected_files
        and totals.verified_files
        == totals.expected_files
        and totals.passed_files
        == totals.expected_files
        and totals.failed_files == 0
        and totals.topology_errors == 0
    )

    runtime_sec = (
        time.perf_counter()
        - started
    )

    diagnostic_manifest = (
        diagnostic_manifest_path(
            metadata_dir=paths.metadata_dir,
            mode=settings.mode,
            run_id=run_id,
            accepted=accepted,
        )
    )
    diagnostic_summary = (
        diagnostic_summary_path(
            metadata_dir=paths.metadata_dir,
            mode=settings.mode,
            run_id=run_id,
            accepted=accepted,
        )
    )

    atomic_write_csv(
        diagnostic_manifest,
        fieldnames=DIAGNOSTIC_MANIFEST_FIELDS,
        rows=(
            result.diagnostic_row(
                settings.mode
            )
            for result in results
        ),
    )

    published_manifest: Path | None = None

    if settings.mode == "fast":
        atomic_write_csv(
            paths.fast_manifest,
            fieldnames=DIAGNOSTIC_MANIFEST_FIELDS,
            rows=(
                result.diagnostic_row(
                    settings.mode
                )
                for result in results
            ),
        )

    elif accepted:
        atomic_write_csv(
            paths.canonical_manifest,
            fieldnames=CANONICAL_MANIFEST_FIELDS,
            rows=(
                result.canonical_row()
                for result in results
            ),
        )
        published_manifest = (
            paths.canonical_manifest
        )

    summary_text = build_summary(
        run_id=run_id,
        settings=settings,
        paths=paths,
        totals=totals,
        accepted=accepted,
        runtime_sec=runtime_sec,
        missing_ranges=missing_ranges,
        extra_ranges=extra_ranges,
        adjacency_issues=adjacency_issues,
        boundary_issues=boundary_issues,
        published_manifest=published_manifest,
        diagnostic_manifest=diagnostic_manifest,
    )

    atomic_write_text(
        diagnostic_summary,
        summary_text,
    )

    if settings.mode == "fast":
        atomic_write_text(
            paths.fast_summary,
            summary_text,
        )

    elif accepted:
        atomic_write_text(
            paths.canonical_summary,
            summary_text,
        )

    run_report = {
        "run_id": run_id,
        "verifier_version": VERIFIER_VERSION,
        "verification_mode": settings.mode,
        "accepted": accepted,
        "runtime_sec": runtime_sec,
        "physical_files": totals.physical_files,
        "expected_files": totals.expected_files,
        "verified_files": totals.verified_files,
        "passed_files": totals.passed_files,
        "failed_files": totals.failed_files,
        "missing_ranges": totals.missing_ranges,
        "extra_ranges": totals.extra_ranges,
        "adjacency_issues": totals.adjacency_issues,
        "boundary_issues": totals.boundary_issues,
        "topology_errors": totals.topology_errors,
        "diagnostic_manifest": str(
            diagnostic_manifest
        ),
        "diagnostic_summary": str(
            diagnostic_summary
        ),
        "canonical_manifest": (
            str(paths.canonical_manifest)
            if published_manifest is not None
            else None
        ),
    }

    atomic_write_json(
        paths.metadata_dir
        / (
            f"repository_verification_"
            f"{run_id}.json"
        ),
        run_report,
    )

    print()
    print("=" * 80)
    print("Verification complete")
    print("=" * 80)
    print(f"Mode             : {settings.mode}")
    print(f"Physical files   : {totals.physical_files}")
    print(f"Expected files   : {totals.expected_files}")
    print(f"Verified files   : {totals.verified_files}")
    print(f"Passed files     : {totals.passed_files}")
    print(f"Failed files     : {totals.failed_files}")
    print(f"Missing ranges   : {totals.missing_ranges}")
    print(f"Extra ranges     : {totals.extra_ranges}")
    print(f"Adjacency issues : {totals.adjacency_issues}")
    print(f"Boundary issues  : {totals.boundary_issues}")
    print(f"Topology errors  : {totals.topology_errors}")
    print(f"Runtime          : {runtime_sec / 60.0:.3f} min")
    print(
        f"Diagnostic       : "
        f"{diagnostic_manifest}"
    )

    if published_manifest is not None:
        print(
            f"Canonical manifest: "
            f"{published_manifest}"
        )
    else:
        print(
            "Canonical manifest: "
            "[UNCHANGED]"
        )

    print("=" * 80)

    if accepted:
        print()
        print("=" * 80)
        print("[ACCEPTED]")
        print(
            "PrimeNet prime repository satisfies "
            f"the {settings.mode} verification contract."
        )
        print("=" * 80)
        return 0

    print()
    print("=" * 80)
    print("[REJECTED]")
    print(
        "PrimeNet prime repository failed "
        "verification."
    )
    print(
        "The canonical manifest was not replaced."
    )
    print("=" * 80)

    return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the canonical PrimeNet "
            "prime repository."
        )
    )

    parser.add_argument(
        "--mode",
        choices=("fast", "full"),
        default="full",
        help=(
            "Verification mode. Fast skips "
            "full monotonic scans and SHA-256. "
            "Default: full."
        ),
    )

    parser.add_argument(
        "--hash-block-size",
        type=int,
        default=DEFAULT_HASH_BLOCK_SIZE,
        help=(
            "SHA-256 read block size in bytes. "
            f"Default: {DEFAULT_HASH_BLOCK_SIZE}"
        ),
    )

    parser.add_argument(
        "--monotonic-chunk-size",
        type=int,
        default=DEFAULT_MONOTONIC_CHUNK_SIZE,
        help=(
            "Elements per chunk for complete "
            "monotonic verification. "
            f"Default: "
            f"{DEFAULT_MONOTONIC_CHUNK_SIZE}"
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        if args.hash_block_size <= 0:
            raise ValueError(
                "hash-block-size must be > 0."
            )

        if args.monotonic_chunk_size <= 0:
            raise ValueError(
                "monotonic-chunk-size must be > 0."
            )

        config = load_platform_config()

        settings = VerifierSettings(
            mode=args.mode,
            expected_start=config.repository_extent.start,
            expected_end=config.repository_extent.end,
            range_size=config.campaign.range_size,
            segment_size=config.campaign.segment_size,
            hash_block_size=args.hash_block_size,
            monotonic_chunk_size=args.monotonic_chunk_size,
        )

        return run_verification(
            config=config,
            settings=settings,
        )

    except (
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