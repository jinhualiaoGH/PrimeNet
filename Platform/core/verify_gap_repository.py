"""
PrimeNet Gap Repository Verifier v3.0.0
=======================================

Certify the canonical left-owned uint16 PrimeNet gap repository.

Mathematical contract
---------------------
For every stored prime p(i), the corresponding gap repository stores:

    g(i) = p(i + 1) - p(i)

Each prime partition owns exactly one outgoing gap per stored prime:

    gap_count == prime_count

For an ordinary partition:
    the final stored gap uses the first prime of the next prime file.

For the terminal repository partition:
    the final stored gap uses the independently computed next prime
    strictly greater than the final stored prime.

Verification modes
------------------
fast:
    Operational readiness verification.

    Checks:
        - exact physical prime inventory;
        - exact physical gap inventory;
        - numeric range adjacency;
        - one-to-one prime/gap range correspondence;
        - prime/gap file loadability;
        - one-dimensional array shape;
        - prime dtype uint64;
        - gap dtype uint16;
        - prime_count == gap_count;
        - nonempty arrays;
        - positive endpoint values;
        - every ordinary boundary gap;
        - the independently computed terminal boundary gap;
        - supported build/canonical manifest structure.

    Skips:
        - complete within-file arithmetic comparison;
        - SHA-256 hashing.

full:
    Formal gap repository certification.

    Performs every fast check plus:
        - complete chunked verification of every local gap;
        - SHA-256 hashing of every gap file.

Artifact ownership
------------------
This module is the certification authority for:

    gap_repository_u16_v3_manifest.csv
    gap_repository_u16_v3_verification_summary.txt

The canonical manifest is atomically replaced only after a complete,
accepted full verification.

Rejected, partial, or interrupted verification never replaces the last
accepted canonical manifest.

Examples
--------
    py -m Platform.core.verify_gap_repository --mode fast

    py -m Platform.core.verify_gap_repository --mode full
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


VERIFIER_NAME = "PrimeNet Gap Repository Verifier"
VERIFIER_VERSION = "3.0.0"

EXPECTED_PRIME_DTYPE = np.dtype(np.uint64)
EXPECTED_GAP_DTYPE = np.dtype(np.uint16)

DEFAULT_ARITHMETIC_CHUNK_SIZE = 10_000_000
DEFAULT_HASH_BLOCK_SIZE = 16 * 1024 * 1024


BUILD_MANIFEST_FIELDS = [
    "gap_file",
    "prime_file",
    "range_start",
    "range_end",
    "dtype",
    "prime_count",
    "gap_count",
    "min_gap",
    "max_gap",
    "first_prime",
    "last_prime",
    "next_prime_used",
    "boundary_gap",
    "terminal_next_prime_computed",
    "file_size_gb",
    "runtime_min",
    "status",
    "created_at",
]


CANONICAL_MANIFEST_FIELDS = [
    "gap_file",
    "prime_file",
    "range_start",
    "range_end",
    "dtype",
    "prime_count",
    "gap_count",
    "min_gap",
    "max_gap",
    "first_prime",
    "last_prime",
    "next_prime_used",
    "boundary_gap",
    "terminal_next_prime_computed",
    "file_size_bytes",
    "file_size_gb",
    "sha256",
    "status",
    "messages",
    "build_created_at",
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
    prime_dir: Path
    gap_dir: Path
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
    arithmetic_chunk_size: int
    hash_block_size: int

    @property
    def full_arithmetic(self) -> bool:
        return self.mode == "full"

    @property
    def hashing_enabled(self) -> bool:
        return self.mode == "full"


@dataclass(frozen=True)
class BuildManifestRow:
    gap_file: str
    prime_file: str
    range_start: int
    range_end: int
    dtype: str
    prime_count: int
    gap_count: int
    min_gap: int
    max_gap: int
    first_prime: int
    last_prime: int
    next_prime_used: int
    boundary_gap: int
    terminal_next_prime_computed: bool
    file_size_gb: float
    runtime_min: float | None
    status: str
    created_at: str


@dataclass(frozen=True)
class GapVerification:
    prime_file: Path
    gap_file: Path
    range_start: int
    range_end: int

    status: str
    messages: tuple[str, ...]

    prime_count: int
    gap_count: int

    min_gap: int | None
    max_gap: int | None

    first_prime: int | None
    last_prime: int | None
    next_prime_used: int | None
    boundary_gap: int | None

    terminal_next_prime_computed: bool

    file_size_bytes: int
    sha256: str

    build_created_at: str
    verified_at: str

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    def canonical_row(self) -> dict[str, Any]:
        return {
            "gap_file": str(self.gap_file),
            "prime_file": str(self.prime_file),
            "range_start": self.range_start,
            "range_end": self.range_end,
            "dtype": (
                "uint16"
                if self.gap_count > 0
                else ""
            ),
            "prime_count": self.prime_count,
            "gap_count": self.gap_count,
            "min_gap": (
                self.min_gap
                if self.min_gap is not None
                else ""
            ),
            "max_gap": (
                self.max_gap
                if self.max_gap is not None
                else ""
            ),
            "first_prime": (
                self.first_prime
                if self.first_prime is not None
                else ""
            ),
            "last_prime": (
                self.last_prime
                if self.last_prime is not None
                else ""
            ),
            "next_prime_used": (
                self.next_prime_used
                if self.next_prime_used is not None
                else ""
            ),
            "boundary_gap": (
                self.boundary_gap
                if self.boundary_gap is not None
                else ""
            ),
            "terminal_next_prime_computed": (
                self.terminal_next_prime_computed
            ),
            "file_size_bytes": self.file_size_bytes,
            "file_size_gb": (
                f"{self.file_size_bytes / (1024 ** 3):.9f}"
            ),
            "sha256": self.sha256,
            "status": self.status,
            "messages": ";".join(self.messages),
            "build_created_at": self.build_created_at,
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
    physical_prime_files: int
    physical_gap_files: int
    expected_files: int
    verified_files: int
    passed_files: int
    failed_files: int

    missing_prime_ranges: int
    extra_prime_ranges: int
    missing_gap_ranges: int
    extra_gap_ranges: int

    prime_adjacency_issues: int
    gap_adjacency_issues: int
    correspondence_issues: int
    boundary_issues: int
    manifest_issues: int

    total_primes: int
    total_gaps: int
    local_gaps_verified: int
    ordinary_boundaries_verified: int
    terminal_boundaries_verified: int

    @property
    def topology_errors(self) -> int:
        return (
            self.missing_prime_ranges
            + self.extra_prime_ranges
            + self.missing_gap_ranges
            + self.extra_gap_ranges
            + self.prime_adjacency_issues
            + self.gap_adjacency_issues
            + self.correspondence_issues
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
        prime_dir=config.paths.ranges_dir,
        gap_dir=config.paths.gaps_dir,
        metadata_dir=metadata_dir,
        canonical_manifest=(
            metadata_dir
            / "gap_repository_u16_v3_manifest.csv"
        ),
        canonical_summary=(
            metadata_dir
            / "gap_repository_u16_v3_verification_summary.txt"
        ),
        fast_manifest=(
            metadata_dir
            / "gap_repository_u16_v3_fast_manifest.csv"
        ),
        fast_summary=(
            metadata_dir
            / "gap_repository_u16_v3_fast_verification_summary.txt"
        ),
    )


def expected_ranges(
    start: int,
    end: int,
    range_size: int,
) -> list[tuple[int, int]]:
    if start < 1:
        raise ValueError(
            "Repository extent start must be >= 1."
        )

    if end < start:
        raise ValueError(
            "Repository extent end must be >= start."
        )

    if range_size <= 0:
        raise ValueError(
            "Repository range size must be > 0."
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


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
        "y",
    }


def require_int(
    row: dict[str, str],
    key: str,
    row_number: int,
) -> int:
    value = row.get(key)

    if value in (None, ""):
        raise ValueError(
            f"Manifest row {row_number}: "
            f"missing {key!r}."
        )

    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Manifest row {row_number}: "
            f"{key!r} must be an integer, "
            f"found {value!r}."
        ) from exc


def optional_float(
    row: dict[str, str],
    key: str,
) -> float | None:
    value = row.get(key)

    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_manifest_rows(
    path: Path,
) -> tuple[
    list[str],
    dict[tuple[int, int], dict[str, str]],
]:
    if not path.is_file():
        return [], {}

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        raw_rows = list(reader)

    if (
        header != BUILD_MANIFEST_FIELDS
        and header != CANONICAL_MANIFEST_FIELDS
    ):
        raise ValueError(
            "Gap manifest schema is unsupported.\n"
            f"Path:  {path}\n"
            f"Found: {header}"
        )

    indexed: dict[
        tuple[int, int],
        dict[str, str],
    ] = {}

    for row_number, row in enumerate(
        raw_rows,
        start=2,
    ):
        start = require_int(
            row,
            "range_start",
            row_number,
        )
        end = require_int(
            row,
            "range_end",
            row_number,
        )
        key = (start, end)

        if key in indexed:
            raise ValueError(
                "Duplicate gap manifest range: "
                f"{start}-{end}"
            )

        indexed[key] = row

    return header, indexed


def build_manifest_row(
    row: dict[str, str] | None,
    row_number: int,
) -> BuildManifestRow | None:
    if row is None:
        return None

    status = (
        row.get("status") or ""
    ).strip().upper()

    created_at = (
        row.get("created_at")
        or row.get("build_created_at")
        or ""
    ).strip()

    return BuildManifestRow(
        gap_file=(
            row.get("gap_file") or ""
        ).strip(),
        prime_file=(
            row.get("prime_file") or ""
        ).strip(),
        range_start=require_int(
            row,
            "range_start",
            row_number,
        ),
        range_end=require_int(
            row,
            "range_end",
            row_number,
        ),
        dtype=(
            row.get("dtype") or ""
        ).strip(),
        prime_count=require_int(
            row,
            "prime_count",
            row_number,
        ),
        gap_count=require_int(
            row,
            "gap_count",
            row_number,
        ),
        min_gap=require_int(
            row,
            "min_gap",
            row_number,
        ),
        max_gap=require_int(
            row,
            "max_gap",
            row_number,
        ),
        first_prime=require_int(
            row,
            "first_prime",
            row_number,
        ),
        last_prime=require_int(
            row,
            "last_prime",
            row_number,
        ),
        next_prime_used=require_int(
            row,
            "next_prime_used",
            row_number,
        ),
        boundary_gap=require_int(
            row,
            "boundary_gap",
            row_number,
        ),
        terminal_next_prime_computed=(
            parse_bool(
                row.get(
                    "terminal_next_prime_computed"
                )
            )
        ),
        file_size_gb=float(
            row.get("file_size_gb") or "0"
        ),
        runtime_min=optional_float(
            row,
            "runtime_min",
        ),
        status=status,
        created_at=created_at,
    )


def is_prime_64(n: int) -> bool:
    """
    Deterministic Miller-Rabin primality test for n < 2**64.
    """
    if n < 2:
        return False

    small_primes = (
        2,
        3,
        5,
        7,
        11,
        13,
        17,
        19,
        23,
        29,
        31,
        37,
    )

    for prime in small_primes:
        if n == prime:
            return True

        if n % prime == 0:
            return False

    d = n - 1
    s = 0

    while d % 2 == 0:
        d //= 2
        s += 1

    bases = (
        2,
        325,
        9_375,
        28_178,
        450_775,
        9_780_504,
        1_795_265_022,
    )

    for base in bases:
        if base % n == 0:
            continue

        value = pow(base, d, n)

        if value in (1, n - 1):
            continue

        for _ in range(s - 1):
            value = pow(
                value,
                2,
                n,
            )

            if value == n - 1:
                break
        else:
            return False

    return True


def next_prime_after(n: int) -> int:
    """
    Return the smallest prime strictly greater than n.
    """
    if n < 2:
        return 2

    candidate = n + 1

    if candidate <= 2:
        return 2

    if candidate % 2 == 0:
        candidate += 1

    while not is_prime_64(candidate):
        candidate += 2

    return candidate


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


def verify_local_gaps(
    primes: np.ndarray,
    gaps: np.ndarray,
    chunk_size: int,
) -> tuple[
    bool,
    int | None,
    int | None,
    int | None,
]:
    """
    Verify every within-file gap in bounded-memory chunks.
    """
    local_gap_count = int(primes.shape[0]) - 1

    for start in range(
        0,
        local_gap_count,
        chunk_size,
    ):
        stop = min(
            start + chunk_size,
            local_gap_count,
        )

        prime_block = primes[
            start:
            stop + 1
        ]
        gap_block = gaps[
            start:
            stop
        ]

        expected = (
            prime_block[1:]
            - prime_block[:-1]
        )

        mismatch_positions = np.flatnonzero(
            expected != gap_block
        )

        if mismatch_positions.size:
            local_offset = int(
                mismatch_positions[0]
            )
            absolute_index = (
                start + local_offset
            )

            return (
                False,
                absolute_index,
                int(expected[local_offset]),
                int(gap_block[local_offset]),
            )

    return True, None, None, None


def verify_one_partition(
    *,
    prime_range: RangeFile,
    gap_range: RangeFile,
    next_prime_range: RangeFile | None,
    settings: VerifierSettings,
    manifest_row: dict[str, str] | None,
    manifest_row_number: int,
) -> tuple[
    GapVerification,
    int,
    int,
    int,
]:
    """
    Verify one aligned prime/gap partition.

    Returns:
        result,
        local_gaps_verified,
        ordinary_boundary_verified,
        terminal_boundary_verified
    """
    verified_at = now_iso()
    messages: list[str] = []

    local_gaps_verified = 0
    ordinary_boundary_verified = 0
    terminal_boundary_verified = 0

    prime_count = 0
    gap_count = 0

    min_gap: int | None = None
    max_gap: int | None = None

    first_prime: int | None = None
    last_prime: int | None = None
    next_prime_used: int | None = None
    boundary_gap: int | None = None

    is_terminal = next_prime_range is None

    file_size_bytes = (
        gap_range.path.stat().st_size
        if gap_range.path.is_file()
        else 0
    )

    checksum = ""
    build_created_at = ""

    build_manifest: BuildManifestRow | None = None

    if manifest_row is not None:
        try:
            build_manifest = build_manifest_row(
                manifest_row,
                manifest_row_number,
            )
            assert build_manifest is not None
            build_created_at = (
                build_manifest.created_at
            )
        except Exception as exc:
            messages.append(
                "manifest_parse_error="
                f"{type(exc).__name__}: {exc}"
            )

    try:
        primes = np.load(
            prime_range.path,
            mmap_mode="r",
            allow_pickle=False,
        )
    except Exception as exc:
        messages.append(
            "prime_load_error="
            f"{type(exc).__name__}: {exc}"
        )
        primes = None

    try:
        gaps = np.load(
            gap_range.path,
            mmap_mode="r",
            allow_pickle=False,
        )
    except Exception as exc:
        messages.append(
            "gap_load_error="
            f"{type(exc).__name__}: {exc}"
        )
        gaps = None

    if primes is not None:
        prime_count = int(primes.size)

        if primes.ndim != 1:
            messages.append(
                f"prime_invalid_shape={primes.shape}"
            )

        if primes.dtype != EXPECTED_PRIME_DTYPE:
            messages.append(
                f"prime_invalid_dtype={primes.dtype}"
            )

        if (
            primes.ndim == 1
            and prime_count > 0
        ):
            first_prime = int(primes[0])
            last_prime = int(primes[-1])

        if prime_count < 2:
            messages.append(
                f"prime_count_too_small={prime_count}"
            )

    if gaps is not None:
        gap_count = int(gaps.size)

        if gaps.ndim != 1:
            messages.append(
                f"gap_invalid_shape={gaps.shape}"
            )

        if gaps.dtype != EXPECTED_GAP_DTYPE:
            messages.append(
                f"gap_invalid_dtype={gaps.dtype}"
            )

        if (
            gaps.ndim == 1
            and gap_count > 0
        ):
            min_gap = int(
                np.min(gaps)
            )
            max_gap = int(
                np.max(gaps)
            )

            if min_gap <= 0:
                messages.append(
                    f"nonpositive_gap={min_gap}"
                )

    if (
        primes is not None
        and gaps is not None
        and prime_count != gap_count
    ):
        messages.append(
            "gap_count_mismatch="
            f"{gap_count}!={prime_count}"
        )

    structural_ok = (
        primes is not None
        and gaps is not None
        and primes.ndim == 1
        and gaps.ndim == 1
        and primes.dtype == EXPECTED_PRIME_DTYPE
        and gaps.dtype == EXPECTED_GAP_DTYPE
        and prime_count >= 2
        and gap_count == prime_count
        and first_prime is not None
        and last_prime is not None
        and min_gap is not None
        and min_gap > 0
    )

    if (
        structural_ok
        and settings.full_arithmetic
    ):
        (
            local_passed,
            mismatch_index,
            expected_gap,
            actual_gap,
        ) = verify_local_gaps(
            primes=primes,
            gaps=gaps,
            chunk_size=(
                settings.arithmetic_chunk_size
            ),
        )

        if not local_passed:
            assert mismatch_index is not None

            messages.append(
                "local_gap_mismatch="
                f"index:{mismatch_index},"
                f"expected:{expected_gap},"
                f"actual:{actual_gap},"
                f"p_i:{int(primes[mismatch_index])},"
                f"p_next:{int(primes[mismatch_index + 1])}"
            )
        else:
            local_gaps_verified = (
                prime_count - 1
            )

    if structural_ok:
        actual_boundary_gap = int(
            gaps[-1]
        )

        if not is_terminal:
            assert next_prime_range is not None

            try:
                next_primes = np.load(
                    next_prime_range.path,
                    mmap_mode="r",
                    allow_pickle=False,
                )

                if (
                    next_primes.ndim != 1
                    or next_primes.size == 0
                    or next_primes.dtype
                    != EXPECTED_PRIME_DTYPE
                ):
                    messages.append(
                        "next_prime_file_invalid"
                    )
                else:
                    next_prime_used = int(
                        next_primes[0]
                    )
                    boundary_gap = (
                        next_prime_used
                        - last_prime
                    )

                    if (
                        actual_boundary_gap
                        != boundary_gap
                    ):
                        messages.append(
                            "ordinary_boundary_mismatch="
                            f"expected:{boundary_gap},"
                            f"actual:{actual_boundary_gap}"
                        )
                    else:
                        ordinary_boundary_verified = 1

            except Exception as exc:
                messages.append(
                    "next_prime_load_error="
                    f"{type(exc).__name__}: {exc}"
                )

        else:
            next_prime_used = next_prime_after(
                last_prime
            )
            boundary_gap = (
                next_prime_used
                - last_prime
            )

            if actual_boundary_gap != boundary_gap:
                messages.append(
                    "terminal_boundary_mismatch="
                    f"expected:{boundary_gap},"
                    f"actual:{actual_boundary_gap}"
                )
            else:
                terminal_boundary_verified = 1

    if build_manifest is not None:
        expected_gap_path = str(
            gap_range.path
        )
        expected_prime_path = str(
            prime_range.path
        )

        comparisons: list[
            tuple[str, Any, Any]
        ] = [
            (
                "range_start",
                prime_range.start,
                build_manifest.range_start,
            ),
            (
                "range_end",
                prime_range.end,
                build_manifest.range_end,
            ),
            (
                "prime_count",
                prime_count,
                build_manifest.prime_count,
            ),
            (
                "gap_count",
                gap_count,
                build_manifest.gap_count,
            ),
            (
                "first_prime",
                first_prime,
                build_manifest.first_prime,
            ),
            (
                "last_prime",
                last_prime,
                build_manifest.last_prime,
            ),
            (
                "next_prime_used",
                next_prime_used,
                build_manifest.next_prime_used,
            ),
            (
                "boundary_gap",
                boundary_gap,
                build_manifest.boundary_gap,
            ),
            (
                "terminal_next_prime_computed",
                is_terminal,
                build_manifest.terminal_next_prime_computed,
            ),
        ]

        for (
            field,
            expected_value,
            actual_value,
        ) in comparisons:
            if expected_value != actual_value:
                messages.append(
                    f"manifest_{field}_mismatch="
                    f"expected:{expected_value},"
                    f"actual:{actual_value}"
                )

        if build_manifest.dtype != "uint16":
            messages.append(
                "manifest_dtype_mismatch="
                f"{build_manifest.dtype!r}"
            )

        if build_manifest.status not in {
            "PASSED",
            "PASS",
        }:
            messages.append(
                "manifest_status_not_passed="
                f"{build_manifest.status!r}"
            )

        if (
            build_manifest.gap_file
            != expected_gap_path
        ):
            messages.append(
                "manifest_gap_file_mismatch"
            )

        if (
            build_manifest.prime_file
            != expected_prime_path
        ):
            messages.append(
                "manifest_prime_file_mismatch"
            )

        if (
            min_gap is not None
            and build_manifest.min_gap
            != min_gap
        ):
            messages.append(
                "manifest_min_gap_mismatch="
                f"expected:{min_gap},"
                f"actual:{build_manifest.min_gap}"
            )

        if (
            max_gap is not None
            and build_manifest.max_gap
            != max_gap
        ):
            messages.append(
                "manifest_max_gap_mismatch="
                f"expected:{max_gap},"
                f"actual:{build_manifest.max_gap}"
            )

        physical_size_gb = (
            file_size_bytes
            / (1024 ** 3)
        )

        if abs(
            build_manifest.file_size_gb
            - physical_size_gb
        ) > 0.000001:
            messages.append(
                "manifest_file_size_mismatch="
                f"expected:{physical_size_gb},"
                f"actual:{build_manifest.file_size_gb}"
            )

    if (
        settings.hashing_enabled
        and not messages
    ):
        try:
            checksum = sha256_file(
                path=gap_range.path,
                block_size=(
                    settings.hash_block_size
                ),
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

    return (
        GapVerification(
            prime_file=prime_range.path,
            gap_file=gap_range.path,
            range_start=prime_range.start,
            range_end=prime_range.end,
            status=status,
            messages=tuple(messages),
            prime_count=prime_count,
            gap_count=gap_count,
            min_gap=min_gap,
            max_gap=max_gap,
            first_prime=first_prime,
            last_prime=last_prime,
            next_prime_used=next_prime_used,
            boundary_gap=boundary_gap,
            terminal_next_prime_computed=(
                is_terminal
            ),
            file_size_bytes=file_size_bytes,
            sha256=checksum,
            build_created_at=build_created_at,
            verified_at=verified_at,
        ),
        local_gaps_verified,
        ordinary_boundary_verified,
        terminal_boundary_verified,
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

        os.replace(
            temporary,
            path,
        )

    finally:
        if temporary.exists():
            temporary.unlink()


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

        os.replace(
            temporary,
            path,
        )

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
            "gap_repository_u16_v3_"
            f"{mode}_verification_"
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
            "gap_repository_u16_v3_"
            f"{mode}_verification_"
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
    missing_prime_ranges: list[
        tuple[int, int]
    ],
    extra_prime_ranges: list[
        tuple[int, int]
    ],
    missing_gap_ranges: list[
        tuple[int, int]
    ],
    extra_gap_ranges: list[
        tuple[int, int]
    ],
    prime_adjacency_issues: list[
        dict[str, Any]
    ],
    gap_adjacency_issues: list[
        dict[str, Any]
    ],
    correspondence_issues: list[
        dict[str, Any]
    ],
    boundary_issues: list[
        dict[str, Any]
    ],
    manifest_issues: list[
        dict[str, Any]
    ],
    diagnostic_manifest: Path,
    published_manifest: Path | None,
) -> str:
    lines = [
        "PrimeNet Gap Repository Verification Summary",
        "==========================================",
        "",
        f"Run ID: {run_id}",
        f"Verified at: {now_iso()}",
        f"Verifier version: {VERIFIER_VERSION}",
        f"Verification mode: {settings.mode}",
        "",
        f"Repository root: {paths.repository_root}",
        f"Prime directory: {paths.prime_dir}",
        f"Gap directory: {paths.gap_dir}",
        "",
        f"Expected start: {settings.expected_start}",
        f"Expected end: {settings.expected_end}",
        f"Range size: {settings.range_size}",
        "",
        f"Physical prime files: {totals.physical_prime_files}",
        f"Physical gap files: {totals.physical_gap_files}",
        f"Expected files: {totals.expected_files}",
        f"Verified files: {totals.verified_files}",
        f"Passed files: {totals.passed_files}",
        f"Failed files: {totals.failed_files}",
        "",
        f"Missing prime ranges: {totals.missing_prime_ranges}",
        f"Extra prime ranges: {totals.extra_prime_ranges}",
        f"Missing gap ranges: {totals.missing_gap_ranges}",
        f"Extra gap ranges: {totals.extra_gap_ranges}",
        f"Prime adjacency issues: {totals.prime_adjacency_issues}",
        f"Gap adjacency issues: {totals.gap_adjacency_issues}",
        f"Correspondence issues: {totals.correspondence_issues}",
        f"Boundary issues: {totals.boundary_issues}",
        f"Manifest issues: {totals.manifest_issues}",
        f"Topology errors: {totals.topology_errors}",
        "",
        f"Total primes: {totals.total_primes}",
        f"Total gaps: {totals.total_gaps}",
        f"Local gaps verified: {totals.local_gaps_verified}",
        (
            "Ordinary boundaries verified: "
            f"{totals.ordinary_boundaries_verified}"
        ),
        (
            "Terminal boundaries verified: "
            f"{totals.terminal_boundaries_verified}"
        ),
        "",
        f"Full local arithmetic: {settings.full_arithmetic}",
        f"SHA-256 hashing: {settings.hashing_enabled}",
        (
            "Arithmetic chunk size: "
            f"{settings.arithmetic_chunk_size}"
        ),
        f"Hash block size: {settings.hash_block_size}",
        "",
        f"Accepted: {accepted}",
        f"Runtime seconds: {runtime_sec:.3f}",
        f"Runtime minutes: {runtime_sec / 60.0:.6f}",
        "",
        f"Diagnostic manifest: {diagnostic_manifest}",
        (
            "Published canonical manifest: "
            f"{published_manifest}"
            if published_manifest is not None
            else (
                "Published canonical manifest: "
                "[UNCHANGED]"
            )
        ),
    ]

    issue_groups: list[
        tuple[str, Iterable[Any]]
    ] = [
        (
            "Missing prime ranges",
            missing_prime_ranges,
        ),
        (
            "Extra prime ranges",
            extra_prime_ranges,
        ),
        (
            "Missing gap ranges",
            missing_gap_ranges,
        ),
        (
            "Extra gap ranges",
            extra_gap_ranges,
        ),
        (
            "Prime adjacency issues",
            prime_adjacency_issues,
        ),
        (
            "Gap adjacency issues",
            gap_adjacency_issues,
        ),
        (
            "Correspondence issues",
            correspondence_issues,
        ),
        (
            "Boundary issues",
            boundary_issues,
        ),
        (
            "Manifest issues",
            manifest_issues,
        ),
    ]

    for title, items in issue_groups:
        materialized = list(items)

        if not materialized:
            continue

        lines.extend(
            [
                "",
                title,
                "-" * len(title),
            ]
        )

        for item in materialized:
            if isinstance(item, tuple):
                lines.append(
                    f"{item[0]} - {item[1]}"
                )
            else:
                lines.append(
                    json.dumps(
                        item,
                        sort_keys=True,
                    )
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
    print(f"Run ID             : {run_id}")
    print(f"Mode               : {settings.mode}")
    print(f"Repository root    : {paths.repository_root}")
    print(f"Prime directory    : {paths.prime_dir}")
    print(f"Gap directory      : {paths.gap_dir}")
    print(
        "Expected extent    : "
        f"{settings.expected_start:,} - "
        f"{settings.expected_end:,}"
    )
    print(
        "Range size         : "
        f"{settings.range_size:,}"
    )
    print(
        "Full arithmetic    : "
        f"{settings.full_arithmetic}"
    )
    print(
        "SHA-256 hashing    : "
        f"{settings.hashing_enabled}"
    )
    print(
        "Canonical manifest : "
        f"{paths.canonical_manifest}"
    )
    print("=" * 80)
    print("Repository law:")
    print("  One stored prime index owns one outgoing gap.")
    print("  g(i) = p(i + 1) - p(i)")
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

    if not paths.prime_dir.is_dir():
        raise FileNotFoundError(
            f"Prime directory not found: "
            f"{paths.prime_dir}"
        )

    if not paths.gap_dir.is_dir():
        raise FileNotFoundError(
            f"Gap directory not found: "
            f"{paths.gap_dir}"
        )

    expected = expected_ranges(
        start=settings.expected_start,
        end=settings.expected_end,
        range_size=settings.range_size,
    )
    expected_keys = set(expected)

    prime_ranges = sorted_range_files(
        paths.prime_dir,
        "primes",
    )
    gap_ranges = sorted_range_files(
        paths.gap_dir,
        "gaps",
    )

    prime_keys = {
        (item.start, item.end)
        for item in prime_ranges
    }
    gap_keys = {
        (item.start, item.end)
        for item in gap_ranges
    }

    missing_prime_ranges = sorted(
        expected_keys - prime_keys
    )
    extra_prime_ranges = sorted(
        prime_keys - expected_keys
    )
    missing_gap_ranges = sorted(
        expected_keys - gap_keys
    )
    extra_gap_ranges = sorted(
        gap_keys - expected_keys
    )

    prime_adjacency_issues = (
        validate_adjacency(prime_ranges)
    )
    gap_adjacency_issues = (
        validate_adjacency(gap_ranges)
    )

    correspondence_issues: list[
        dict[str, Any]
    ] = []

    for key in sorted(
        (prime_keys | gap_keys)
    ):
        if (
            key in prime_keys
            and key not in gap_keys
        ):
            correspondence_issues.append(
                {
                    "issue_type": "MISSING_GAP",
                    "range_start": key[0],
                    "range_end": key[1],
                }
            )

        elif (
            key in gap_keys
            and key not in prime_keys
        ):
            correspondence_issues.append(
                {
                    "issue_type": "ORPHAN_GAP",
                    "range_start": key[0],
                    "range_end": key[1],
                }
            )

    manifest_header: list[str] = []
    manifest_rows: dict[
        tuple[int, int],
        dict[str, str],
    ] = {}
    manifest_issues: list[
        dict[str, Any]
    ] = []

    try:
        (
            manifest_header,
            manifest_rows,
        ) = load_manifest_rows(
            paths.canonical_manifest
        )
    except Exception as exc:
        manifest_issues.append(
            {
                "issue_type": "MANIFEST_LOAD",
                "message": (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            }
        )

    manifest_keys = set(
        manifest_rows
    )

    for key in sorted(
        manifest_keys - expected_keys
    ):
        manifest_issues.append(
            {
                "issue_type": "EXTRA_MANIFEST_RANGE",
                "range_start": key[0],
                "range_end": key[1],
            }
        )

    print()
    print("Repository topology")
    print("-" * 80)
    print(
        f"Physical prime files : "
        f"{len(prime_ranges)}"
    )
    print(
        f"Physical gap files   : "
        f"{len(gap_ranges)}"
    )
    print(
        f"Expected files       : "
        f"{len(expected)}"
    )
    print(
        f"Missing prime ranges : "
        f"{len(missing_prime_ranges)}"
    )
    print(
        f"Extra prime ranges   : "
        f"{len(extra_prime_ranges)}"
    )
    print(
        f"Missing gap ranges   : "
        f"{len(missing_gap_ranges)}"
    )
    print(
        f"Extra gap ranges     : "
        f"{len(extra_gap_ranges)}"
    )
    print(
        f"Prime adjacency      : "
        f"{len(prime_adjacency_issues)}"
    )
    print(
        f"Gap adjacency        : "
        f"{len(gap_adjacency_issues)}"
    )
    print(
        f"Correspondence issues: "
        f"{len(correspondence_issues)}"
    )
    print(
        f"Manifest rows        : "
        f"{len(manifest_rows)}"
    )
    print(
        f"Manifest issues      : "
        f"{len(manifest_issues)}"
    )

    prime_map = {
        (item.start, item.end): item
        for item in prime_ranges
    }
    gap_map = {
        (item.start, item.end): item
        for item in gap_ranges
    }

    results: list[
        GapVerification
    ] = []

    local_gaps_verified = 0
    ordinary_boundaries_verified = 0
    terminal_boundaries_verified = 0

    boundary_issues: list[
        dict[str, Any]
    ] = []

    for index, key in enumerate(
        expected,
        start=1,
    ):
        start, end = key

        print()
        print("-" * 80)
        print(
            f"[{index}/{len(expected)}] "
            f"{start:,} - {end:,}"
        )

        prime_range = prime_map.get(key)
        gap_range = gap_map.get(key)

        if (
            prime_range is None
            or gap_range is None
        ):
            missing_messages: list[str] = []

            if prime_range is None:
                missing_messages.append(
                    "prime_file_missing"
                )

            if gap_range is None:
                missing_messages.append(
                    "gap_file_missing"
                )

            synthetic_prime_path = (
                paths.prime_dir
                / f"primes_{start}_{end}.npy"
            )
            synthetic_gap_path = (
                paths.gap_dir
                / f"gaps_{start}_{end}.npy"
            )

            result = GapVerification(
                prime_file=synthetic_prime_path,
                gap_file=synthetic_gap_path,
                range_start=start,
                range_end=end,
                status="missing",
                messages=tuple(
                    missing_messages
                ),
                prime_count=0,
                gap_count=0,
                min_gap=None,
                max_gap=None,
                first_prime=None,
                last_prime=None,
                next_prime_used=None,
                boundary_gap=None,
                terminal_next_prime_computed=(
                    index == len(expected)
                ),
                file_size_bytes=0,
                sha256="",
                build_created_at="",
                verified_at=now_iso(),
            )
            results.append(result)

            print(
                "[MISSING] "
                + ";".join(
                    missing_messages
                )
            )
            continue

        next_prime_range: (
            RangeFile | None
        ) = None

        if index < len(expected):
            next_key = expected[index]
            next_prime_range = (
                prime_map.get(next_key)
            )

        manifest_row = (
            manifest_rows.get(key)
        )

        (
            result,
            local_count,
            ordinary_count,
            terminal_count,
        ) = verify_one_partition(
            prime_range=prime_range,
            gap_range=gap_range,
            next_prime_range=(
                next_prime_range
            ),
            settings=settings,
            manifest_row=manifest_row,
            manifest_row_number=(
                index + 1
            ),
        )

        results.append(result)

        local_gaps_verified += (
            local_count
        )
        ordinary_boundaries_verified += (
            ordinary_count
        )
        terminal_boundaries_verified += (
            terminal_count
        )

        if (
            result.boundary_gap is None
            or (
                index < len(expected)
                and ordinary_count == 0
            )
            or (
                index == len(expected)
                and terminal_count == 0
            )
        ):
            boundary_issues.append(
                {
                    "issue_type": (
                        "TERMINAL_BOUNDARY"
                        if index == len(expected)
                        else "ORDINARY_BOUNDARY"
                    ),
                    "range_start": start,
                    "range_end": end,
                    "messages": list(
                        result.messages
                    ),
                }
            )

        if result.passed:
            print(
                "[PASSED] "
                f"primes={result.prime_count:,}, "
                f"gaps={result.gap_count:,}, "
                f"min_gap={result.min_gap}, "
                f"max_gap={result.max_gap}, "
                f"boundary={result.boundary_gap}"
            )
        else:
            print(
                f"[{result.status.upper()}] "
                + ";".join(
                    result.messages
                )
            )

    total_primes = sum(
        result.prime_count
        for result in results
    )
    total_gaps = sum(
        result.gap_count
        for result in results
    )
    passed_files = sum(
        result.passed
        for result in results
    )
    failed_files = sum(
        not result.passed
        for result in results
    )

    totals = VerificationTotals(
        physical_prime_files=(
            len(prime_ranges)
        ),
        physical_gap_files=(
            len(gap_ranges)
        ),
        expected_files=len(expected),
        verified_files=len(results),
        passed_files=passed_files,
        failed_files=failed_files,
        missing_prime_ranges=(
            len(missing_prime_ranges)
        ),
        extra_prime_ranges=(
            len(extra_prime_ranges)
        ),
        missing_gap_ranges=(
            len(missing_gap_ranges)
        ),
        extra_gap_ranges=(
            len(extra_gap_ranges)
        ),
        prime_adjacency_issues=(
            len(prime_adjacency_issues)
        ),
        gap_adjacency_issues=(
            len(gap_adjacency_issues)
        ),
        correspondence_issues=(
            len(correspondence_issues)
        ),
        boundary_issues=(
            len(boundary_issues)
        ),
        manifest_issues=(
            len(manifest_issues)
        ),
        total_primes=total_primes,
        total_gaps=total_gaps,
        local_gaps_verified=(
            local_gaps_verified
        ),
        ordinary_boundaries_verified=(
            ordinary_boundaries_verified
        ),
        terminal_boundaries_verified=(
            terminal_boundaries_verified
        ),
    )

    expected_local_gaps = (
        total_primes
        - len(expected)
    )
    expected_ordinary_boundaries = (
        len(expected) - 1
    )

    accepted = (
        totals.physical_prime_files
        == totals.expected_files
        and totals.physical_gap_files
        == totals.expected_files
        and totals.verified_files
        == totals.expected_files
        and totals.passed_files
        == totals.expected_files
        and totals.failed_files == 0
        and totals.topology_errors == 0
        and totals.boundary_issues == 0
        and totals.manifest_issues == 0
        and totals.total_primes
        == totals.total_gaps
        and (
            not settings.full_arithmetic
            or totals.local_gaps_verified
            == expected_local_gaps
        )
        and totals.ordinary_boundaries_verified
        == expected_ordinary_boundaries
        and totals.terminal_boundaries_verified
        == 1
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
        fieldnames=(
            DIAGNOSTIC_MANIFEST_FIELDS
        ),
        rows=(
            result.diagnostic_row(
                settings.mode
            )
            for result in results
        ),
    )

    published_manifest: (
        Path | None
    ) = None

    if settings.mode == "fast":
        atomic_write_csv(
            paths.fast_manifest,
            fieldnames=(
                DIAGNOSTIC_MANIFEST_FIELDS
            ),
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
            fieldnames=(
                CANONICAL_MANIFEST_FIELDS
            ),
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
        missing_prime_ranges=(
            missing_prime_ranges
        ),
        extra_prime_ranges=(
            extra_prime_ranges
        ),
        missing_gap_ranges=(
            missing_gap_ranges
        ),
        extra_gap_ranges=(
            extra_gap_ranges
        ),
        prime_adjacency_issues=(
            prime_adjacency_issues
        ),
        gap_adjacency_issues=(
            gap_adjacency_issues
        ),
        correspondence_issues=(
            correspondence_issues
        ),
        boundary_issues=(
            boundary_issues
        ),
        manifest_issues=(
            manifest_issues
        ),
        diagnostic_manifest=(
            diagnostic_manifest
        ),
        published_manifest=(
            published_manifest
        ),
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

    atomic_write_json(
        paths.metadata_dir
        / (
            "gap_repository_u16_v3_"
            f"verification_{run_id}.json"
        ),
        {
            "run_id": run_id,
            "verifier_version": (
                VERIFIER_VERSION
            ),
            "verification_mode": (
                settings.mode
            ),
            "accepted": accepted,
            "runtime_sec": runtime_sec,
            "physical_prime_files": (
                totals.physical_prime_files
            ),
            "physical_gap_files": (
                totals.physical_gap_files
            ),
            "expected_files": (
                totals.expected_files
            ),
            "verified_files": (
                totals.verified_files
            ),
            "passed_files": (
                totals.passed_files
            ),
            "failed_files": (
                totals.failed_files
            ),
            "topology_errors": (
                totals.topology_errors
            ),
            "boundary_issues": (
                totals.boundary_issues
            ),
            "manifest_issues": (
                totals.manifest_issues
            ),
            "total_primes": (
                totals.total_primes
            ),
            "total_gaps": (
                totals.total_gaps
            ),
            "local_gaps_verified": (
                totals.local_gaps_verified
            ),
            "ordinary_boundaries_verified": (
                totals.ordinary_boundaries_verified
            ),
            "terminal_boundaries_verified": (
                totals.terminal_boundaries_verified
            ),
            "diagnostic_manifest": str(
                diagnostic_manifest
            ),
            "diagnostic_summary": str(
                diagnostic_summary
            ),
            "canonical_manifest": (
                str(published_manifest)
                if published_manifest
                is not None
                else None
            ),
        },
    )

    print()
    print("=" * 80)
    print("Gap repository verification complete")
    print("=" * 80)
    print(
        f"Mode                  : "
        f"{settings.mode}"
    )
    print(
        f"Physical prime files  : "
        f"{totals.physical_prime_files}"
    )
    print(
        f"Physical gap files    : "
        f"{totals.physical_gap_files}"
    )
    print(
        f"Expected files        : "
        f"{totals.expected_files}"
    )
    print(
        f"Verified files        : "
        f"{totals.verified_files}"
    )
    print(
        f"Passed files          : "
        f"{totals.passed_files}"
    )
    print(
        f"Failed files          : "
        f"{totals.failed_files}"
    )
    print(
        f"Topology errors       : "
        f"{totals.topology_errors}"
    )
    print(
        f"Boundary issues       : "
        f"{totals.boundary_issues}"
    )
    print(
        f"Manifest issues       : "
        f"{totals.manifest_issues}"
    )
    print(
        f"Total primes          : "
        f"{totals.total_primes:,}"
    )
    print(
        f"Total gaps            : "
        f"{totals.total_gaps:,}"
    )
    print(
        f"Local gaps verified   : "
        f"{totals.local_gaps_verified:,}"
    )
    print(
        "Ordinary boundaries   : "
        f"{totals.ordinary_boundaries_verified}"
    )
    print(
        "Terminal boundaries   : "
        f"{totals.terminal_boundaries_verified}"
    )
    print(
        f"Runtime               : "
        f"{runtime_sec / 60.0:.3f} min"
    )
    print(
        f"Diagnostic manifest   : "
        f"{diagnostic_manifest}"
    )

    if published_manifest is not None:
        print(
            f"Canonical manifest    : "
            f"{published_manifest}"
        )
    else:
        print(
            "Canonical manifest    : "
            "[UNCHANGED]"
        )

    print("=" * 80)

    if accepted:
        print()
        print("=" * 80)
        print("[ACCEPTED]")
        print(
            "PrimeNet gaps_u16_v3 satisfies "
            f"the {settings.mode} "
            "index-coordinate contract."
        )
        print()
        print(
            "For every stored prime index i:"
        )
        print(
            "    g(i) = p(i + 1) - p(i)"
        )
        print("=" * 80)
        return 0

    print()
    print("=" * 80)
    print("[REJECTED]")
    print(
        "The gap repository failed "
        "verification."
    )
    print(
        "The canonical gap manifest "
        "was not replaced."
    )
    print("=" * 80)

    return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the canonical PrimeNet "
            "left-owned uint16 gap repository."
        )
    )

    parser.add_argument(
        "--mode",
        choices=("fast", "full"),
        default="full",
        help=(
            "Verification mode. Fast skips "
            "complete local arithmetic and SHA-256. "
            "Default: full."
        ),
    )

    parser.add_argument(
        "--arithmetic-chunk-size",
        type=int,
        default=(
            DEFAULT_ARITHMETIC_CHUNK_SIZE
        ),
        help=(
            "Local gaps checked per chunk. "
            f"Default: "
            f"{DEFAULT_ARITHMETIC_CHUNK_SIZE}"
        ),
    )

    parser.add_argument(
        "--hash-block-size",
        type=int,
        default=DEFAULT_HASH_BLOCK_SIZE,
        help=(
            "SHA-256 read block size in bytes. "
            f"Default: "
            f"{DEFAULT_HASH_BLOCK_SIZE}"
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        if args.arithmetic_chunk_size <= 0:
            raise ValueError(
                "arithmetic-chunk-size "
                "must be > 0."
            )

        if args.hash_block_size <= 0:
            raise ValueError(
                "hash-block-size must be > 0."
            )

        config = load_platform_config()

        settings = VerifierSettings(
            mode=args.mode,
            expected_start=(
                config.repository_extent.start
            ),
            expected_end=(
                config.repository_extent.end
            ),
            range_size=(
                config.campaign.range_size
            ),
            arithmetic_chunk_size=(
                args.arithmetic_chunk_size
            ),
            hash_block_size=(
                args.hash_block_size
            ),
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