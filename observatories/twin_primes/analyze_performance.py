"""
PrimeNet Twin-Prime Performance Analyzer
========================================

Canonical, read-only performance analysis for the accepted PrimeNet
1–3T Twin Prime Census.

The analyzer consumes:

    twin_prime_census_1_3T.csv
    twin_prime_census_1_3T_summary.json

It validates the scientific and operational contracts, calculates full-run
and steady-state performance profiles, and optionally publishes:

    twin_prime_performance_analysis.json
    twin_prime_performance_report.txt

Design principles
-----------------
- Scientific census inputs are never modified.
- Existing outputs are protected unless --overwrite is explicit.
- Published files are replaced atomically.
- --dry-run performs complete validation and analysis without writing files.
- Importing this module has no filesystem side effects.
- Full-run and steady-state statistics are reported separately.
- Startup partitions are retained transparently rather than silently removed.

Typical usage
-------------

    py -B -m observatories.twin_primes.analyze_performance --dry-run

    py -B -m observatories.twin_primes.analyze_performance

    py -B -m observatories.twin_primes.analyze_performance --overwrite
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import sys
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


ANALYZER_VERSION = "1.0.0"

DEFAULT_REPOSITORY_ROOT = Path(r"E:\PrimeNet\Repository")
DEFAULT_OBSERVATION_DIR = (
    DEFAULT_REPOSITORY_ROOT
    / "observations"
    / "twin_primes"
)

DEFAULT_CENSUS_CSV = (
    DEFAULT_OBSERVATION_DIR
    / "twin_prime_census_1_3T.csv"
)

DEFAULT_CENSUS_SUMMARY = (
    DEFAULT_OBSERVATION_DIR
    / "twin_prime_census_1_3T_summary.json"
)

DEFAULT_ANALYSIS_JSON = (
    DEFAULT_OBSERVATION_DIR
    / "twin_prime_performance_analysis.json"
)

DEFAULT_REPORT_TXT = (
    DEFAULT_OBSERVATION_DIR
    / "twin_prime_performance_report.txt"
)

EXPECTED_PARTITIONS = 300
EXPECTED_DOMAIN_START = 1
EXPECTED_DOMAIN_END = 3_000_000_000_000
EXPECTED_TOTAL_GAPS = 108_340_298_703
EXPECTED_TOTAL_TWINS = 5_173_760_785
EXPECTED_EVENT_DEFINITION = "g(i) = 2"
EXPECTED_REPOSITORY = (
    DEFAULT_REPOSITORY_ROOT
    / "gaps"
)

REQUIRED_CSV_FIELDS = (
    "partition",
    "range_start",
    "range_end",
    "gap_count",
    "twin_count",
    "twin_density",
    "cumulative_gap_count",
    "cumulative_twin_count",
    "cumulative_twin_density",
    "runtime_sec",
)

SEPARATOR = "=" * 80
SUBSEPARATOR = "-" * 80


@dataclass(frozen=True)
class AnalyzerSettings:
    """Command-line settings resolved to concrete paths."""

    census_csv: Path
    census_summary: Path
    analysis_json: Path
    report_txt: Path
    overwrite: bool
    dry_run: bool


@dataclass(frozen=True)
class CensusRow:
    """Validated partition-level census observation."""

    partition: int
    range_start: int
    range_end: int
    gap_count: int
    twin_count: int
    twin_density: float
    cumulative_gap_count: int
    cumulative_twin_count: int
    cumulative_twin_density: float
    runtime_sec: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CensusSummary:
    """Validated canonical census summary."""

    project: str
    instrument: str
    version: str
    repository: str
    repository_status: str
    numeric_domain_start: int
    numeric_domain_end: int
    event_definition: str
    gap_files_scanned: int
    total_gaps_scanned: int
    total_twin_prime_events: int
    global_twin_density: float
    runtime_seconds: float
    runtime_minutes: float
    csv_output: str
    generated_at_utc: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PerformanceWindow:
    """Performance statistics for one transparent analysis window."""

    name: str
    description: str
    first_partition: int
    last_partition: int
    partitions: int

    total_gaps: int
    total_twins: int
    total_runtime_sec: float
    total_runtime_min: float

    mean_runtime_sec: float
    median_runtime_sec: float
    minimum_runtime_sec: float
    maximum_runtime_sec: float
    runtime_stddev_sec: float
    runtime_cv: float

    p05_runtime_sec: float
    p25_runtime_sec: float
    p50_runtime_sec: float
    p75_runtime_sec: float
    p95_runtime_sec: float
    p99_runtime_sec: float

    sustained_gaps_per_sec: float
    sustained_gaps_per_min: float
    median_partition_gaps_per_sec: float
    minimum_partition_gaps_per_sec: float
    maximum_partition_gaps_per_sec: float

    gap_count_runtime_correlation: float
    partition_index_runtime_correlation: float

    fastest_partition: int
    fastest_partition_runtime_sec: float
    fastest_partition_gap_count: int

    slowest_partition: int
    slowest_partition_runtime_sec: float
    slowest_partition_gap_count: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PerformanceAnalysis:
    """Complete canonical performance-analysis result."""

    analyzer_version: str
    analysis_id: str
    generated_at_utc: str

    census_csv: str
    census_summary: str
    canonical_repository: str

    census_version: str
    census_generated_at_utc: str

    numeric_domain_start: int
    numeric_domain_end: int
    event_definition: str

    partitions: int
    total_gaps: int
    total_twins: int
    global_twin_density: float

    csv_partition_runtime_sec: float
    summary_end_to_end_runtime_sec: float
    runtime_accounting_difference_sec: float
    runtime_accounting_ratio: float

    windows: tuple[PerformanceWindow, ...]

    startup_profile: tuple[dict[str, Any], ...]
    final_profile: tuple[dict[str, Any], ...]

    accepted: bool
    validation_messages: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "analyzer_version": self.analyzer_version,
            "analysis_id": self.analysis_id,
            "generated_at_utc": self.generated_at_utc,
            "inputs": {
                "census_csv": self.census_csv,
                "census_summary": self.census_summary,
                "canonical_repository": self.canonical_repository,
                "census_version": self.census_version,
                "census_generated_at_utc": (
                    self.census_generated_at_utc
                ),
            },
            "scientific_domain": {
                "numeric_domain_start": (
                    self.numeric_domain_start
                ),
                "numeric_domain_end": (
                    self.numeric_domain_end
                ),
                "event_definition": (
                    self.event_definition
                ),
                "partitions": self.partitions,
                "total_gaps": self.total_gaps,
                "total_twins": self.total_twins,
                "global_twin_density": (
                    self.global_twin_density
                ),
            },
            "runtime_accounting": {
                "csv_partition_runtime_sec": (
                    self.csv_partition_runtime_sec
                ),
                "summary_end_to_end_runtime_sec": (
                    self.summary_end_to_end_runtime_sec
                ),
                "difference_sec": (
                    self.runtime_accounting_difference_sec
                ),
                "partition_runtime_fraction": (
                    self.runtime_accounting_ratio
                ),
            },
            "performance_windows": [
                window.as_dict()
                for window in self.windows
            ],
            "startup_profile": list(
                self.startup_profile
            ),
            "final_profile": list(
                self.final_profile
            ),
            "accepted": self.accepted,
            "validation_messages": list(
                self.validation_messages
            ),
        }


def utc_now_iso() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


def new_analysis_id() -> str:
    """Create a compact, collision-resistant analysis identifier."""

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d_%H%M%S")

    suffix = uuid.uuid4().hex[:8]

    return f"{timestamp}_{suffix}"


def parse_int(
    value: str,
    *,
    field_name: str,
    row_number: int,
) -> int:
    """Parse and validate an integer CSV field."""

    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"CSV row {row_number}: "
            f"{field_name} must be an integer; "
            f"found {value!r}."
        ) from exc

    return parsed


def parse_float(
    value: str,
    *,
    field_name: str,
    row_number: int,
) -> float:
    """Parse and validate a finite floating-point CSV field."""

    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"CSV row {row_number}: "
            f"{field_name} must be numeric; "
            f"found {value!r}."
        ) from exc

    if not math.isfinite(parsed):
        raise ValueError(
            f"CSV row {row_number}: "
            f"{field_name} must be finite; "
            f"found {value!r}."
        )

    return parsed


def read_census_rows(
    path: Path,
) -> list[CensusRow]:
    """Read and validate the canonical partition census CSV."""

    if not path.is_file():
        raise FileNotFoundError(
            f"Census CSV does not exist: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        if reader.fieldnames is None:
            raise ValueError(
                f"Census CSV has no header: {path}"
            )

        missing_fields = [
            field
            for field in REQUIRED_CSV_FIELDS
            if field not in reader.fieldnames
        ]

        if missing_fields:
            raise ValueError(
                "Census CSV is missing required fields: "
                + ", ".join(missing_fields)
            )

        rows: list[CensusRow] = []

        for row_number, raw in enumerate(
            reader,
            start=2,
        ):
            row = CensusRow(
                partition=parse_int(
                    raw["partition"],
                    field_name="partition",
                    row_number=row_number,
                ),
                range_start=parse_int(
                    raw["range_start"],
                    field_name="range_start",
                    row_number=row_number,
                ),
                range_end=parse_int(
                    raw["range_end"],
                    field_name="range_end",
                    row_number=row_number,
                ),
                gap_count=parse_int(
                    raw["gap_count"],
                    field_name="gap_count",
                    row_number=row_number,
                ),
                twin_count=parse_int(
                    raw["twin_count"],
                    field_name="twin_count",
                    row_number=row_number,
                ),
                twin_density=parse_float(
                    raw["twin_density"],
                    field_name="twin_density",
                    row_number=row_number,
                ),
                cumulative_gap_count=parse_int(
                    raw["cumulative_gap_count"],
                    field_name="cumulative_gap_count",
                    row_number=row_number,
                ),
                cumulative_twin_count=parse_int(
                    raw["cumulative_twin_count"],
                    field_name="cumulative_twin_count",
                    row_number=row_number,
                ),
                cumulative_twin_density=parse_float(
                    raw["cumulative_twin_density"],
                    field_name=(
                        "cumulative_twin_density"
                    ),
                    row_number=row_number,
                ),
                runtime_sec=parse_float(
                    raw["runtime_sec"],
                    field_name="runtime_sec",
                    row_number=row_number,
                ),
            )

            validate_census_row(
                row,
                row_number=row_number,
            )

            rows.append(row)

    if not rows:
        raise ValueError(
            f"Census CSV contains no records: {path}"
        )

    return rows


def validate_census_row(
    row: CensusRow,
    *,
    row_number: int,
) -> None:
    """Validate one partition record."""

    if row.partition < 1:
        raise ValueError(
            f"CSV row {row_number}: "
            "partition must be >= 1."
        )

    if row.range_start < 1:
        raise ValueError(
            f"CSV row {row_number}: "
            "range_start must be >= 1."
        )

    if row.range_end < row.range_start:
        raise ValueError(
            f"CSV row {row_number}: "
            "range_end must be >= range_start."
        )

    if row.gap_count <= 0:
        raise ValueError(
            f"CSV row {row_number}: "
            "gap_count must be positive."
        )

    if row.twin_count < 0:
        raise ValueError(
            f"CSV row {row_number}: "
            "twin_count must be nonnegative."
        )

    if row.twin_count > row.gap_count:
        raise ValueError(
            f"CSV row {row_number}: "
            "twin_count cannot exceed gap_count."
        )

    if row.runtime_sec <= 0.0:
        raise ValueError(
            f"CSV row {row_number}: "
            "runtime_sec must be positive."
        )

    expected_density = (
        row.twin_count
        / row.gap_count
    )

    if not math.isclose(
        row.twin_density,
        expected_density,
        rel_tol=1e-12,
        abs_tol=1e-15,
    ):
        raise ValueError(
            f"CSV row {row_number}: "
            "twin_density does not match "
            "twin_count / gap_count."
        )


def read_census_summary(
    path: Path,
) -> CensusSummary:
    """Read and validate the canonical census JSON summary."""

    if not path.is_file():
        raise FileNotFoundError(
            f"Census summary does not exist: {path}"
        )

    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8-sig"
            )
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON summary: {path}"
        ) from exc

    required = (
        "project",
        "instrument",
        "version",
        "repository",
        "repository_status",
        "numeric_domain_start",
        "numeric_domain_end",
        "event_definition",
        "gap_files_scanned",
        "total_gaps_scanned",
        "total_twin_prime_events",
        "global_twin_density",
        "runtime_seconds",
        "runtime_minutes",
        "csv_output",
        "generated_at_utc",
    )

    missing = [
        key
        for key in required
        if key not in payload
    ]

    if missing:
        raise ValueError(
            "Census summary is missing required fields: "
            + ", ".join(missing)
        )

    summary = CensusSummary(
        project=str(payload["project"]),
        instrument=str(payload["instrument"]),
        version=str(payload["version"]),
        repository=str(payload["repository"]),
        repository_status=str(
            payload["repository_status"]
        ),
        numeric_domain_start=int(
            payload["numeric_domain_start"]
        ),
        numeric_domain_end=int(
            payload["numeric_domain_end"]
        ),
        event_definition=str(
            payload["event_definition"]
        ),
        gap_files_scanned=int(
            payload["gap_files_scanned"]
        ),
        total_gaps_scanned=int(
            payload["total_gaps_scanned"]
        ),
        total_twin_prime_events=int(
            payload["total_twin_prime_events"]
        ),
        global_twin_density=float(
            payload["global_twin_density"]
        ),
        runtime_seconds=float(
            payload["runtime_seconds"]
        ),
        runtime_minutes=float(
            payload["runtime_minutes"]
        ),
        csv_output=str(
            payload["csv_output"]
        ),
        generated_at_utc=str(
            payload["generated_at_utc"]
        ),
    )

    if not math.isfinite(
        summary.runtime_seconds
    ):
        raise ValueError(
            "Summary runtime_seconds must be finite."
        )

    if summary.runtime_seconds <= 0.0:
        raise ValueError(
            "Summary runtime_seconds must be positive."
        )

    return summary


def validate_census_contract(
    rows: Sequence[CensusRow],
    summary: CensusSummary,
) -> list[str]:
    """
    Validate scientific, topology, cumulative, and summary correspondence.
    """

    messages: list[str] = []

    if len(rows) != EXPECTED_PARTITIONS:
        raise ValueError(
            f"Expected {EXPECTED_PARTITIONS} partitions, "
            f"found {len(rows)}."
        )

    expected_partition = 1
    previous_end: int | None = None
    cumulative_gaps = 0
    cumulative_twins = 0

    for row in rows:
        if row.partition != expected_partition:
            raise ValueError(
                "Partition numbering mismatch: "
                f"expected {expected_partition}, "
                f"found {row.partition}."
            )

        if previous_end is not None:
            expected_start = previous_end + 1

            if row.range_start != expected_start:
                raise ValueError(
                    "Partition adjacency mismatch: "
                    f"partition {row.partition} starts at "
                    f"{row.range_start}, expected "
                    f"{expected_start}."
                )

        cumulative_gaps += row.gap_count
        cumulative_twins += row.twin_count

        if (
            row.cumulative_gap_count
            != cumulative_gaps
        ):
            raise ValueError(
                "Cumulative gap count mismatch at "
                f"partition {row.partition}."
            )

        if (
            row.cumulative_twin_count
            != cumulative_twins
        ):
            raise ValueError(
                "Cumulative twin count mismatch at "
                f"partition {row.partition}."
            )

        expected_cumulative_density = (
            cumulative_twins
            / cumulative_gaps
        )

        if not math.isclose(
            row.cumulative_twin_density,
            expected_cumulative_density,
            rel_tol=1e-12,
            abs_tol=1e-15,
        ):
            raise ValueError(
                "Cumulative twin density mismatch at "
                f"partition {row.partition}."
            )

        previous_end = row.range_end
        expected_partition += 1

    first = rows[0]
    last = rows[-1]

    if first.range_start != EXPECTED_DOMAIN_START:
        raise ValueError(
            "Unexpected numeric-domain start: "
            f"{first.range_start}."
        )

    if last.range_end != EXPECTED_DOMAIN_END:
        raise ValueError(
            "Unexpected numeric-domain end: "
            f"{last.range_end}."
        )

    total_gaps = sum(
        row.gap_count
        for row in rows
    )

    total_twins = sum(
        row.twin_count
        for row in rows
    )

    expected_density = (
        total_twins
        / total_gaps
    )

    if total_gaps != EXPECTED_TOTAL_GAPS:
        raise ValueError(
            "Canonical total-gap mismatch: "
            f"expected {EXPECTED_TOTAL_GAPS}, "
            f"found {total_gaps}."
        )

    if total_twins != EXPECTED_TOTAL_TWINS:
        raise ValueError(
            "Canonical twin-event mismatch: "
            f"expected {EXPECTED_TOTAL_TWINS}, "
            f"found {total_twins}."
        )

    if (
        summary.repository_status.upper()
        != "ACCEPTED"
    ):
        raise ValueError(
            "Census summary is not accepted: "
            f"{summary.repository_status!r}."
        )

    if (
        Path(summary.repository)
        != EXPECTED_REPOSITORY
    ):
        raise ValueError(
            "Census summary repository mismatch: "
            f"expected {EXPECTED_REPOSITORY}, "
            f"found {summary.repository}."
        )

    if (
        summary.numeric_domain_start
        != EXPECTED_DOMAIN_START
    ):
        raise ValueError(
            "Summary numeric-domain start mismatch."
        )

    if (
        summary.numeric_domain_end
        != EXPECTED_DOMAIN_END
    ):
        raise ValueError(
            "Summary numeric-domain end mismatch."
        )

    if (
        summary.event_definition
        != EXPECTED_EVENT_DEFINITION
    ):
        raise ValueError(
            "Summary event definition mismatch."
        )

    if (
        summary.gap_files_scanned
        != len(rows)
    ):
        raise ValueError(
            "Summary partition-count mismatch."
        )

    if (
        summary.total_gaps_scanned
        != total_gaps
    ):
        raise ValueError(
            "Summary total-gap mismatch."
        )

    if (
        summary.total_twin_prime_events
        != total_twins
    ):
        raise ValueError(
            "Summary twin-event mismatch."
        )

    if not math.isclose(
        summary.global_twin_density,
        expected_density,
        rel_tol=1e-15,
        abs_tol=0.0,
    ):
        raise ValueError(
            "Summary global twin density mismatch."
        )

    expected_runtime_minutes = (
        summary.runtime_seconds
        / 60.0
    )

    if not math.isclose(
        summary.runtime_minutes,
        expected_runtime_minutes,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "Summary runtime minute/second mismatch."
        )

    messages.extend(
        (
            "Partition count contract passed.",
            "Partition adjacency contract passed.",
            "Cumulative-count contract passed.",
            "Scientific-total contract passed.",
            "Canonical repository contract passed.",
            "Accepted summary correspondence passed.",
        )
    )

    return messages


def percentile(
    values: Sequence[float],
    probability: float,
) -> float:
    """
    Return a linearly interpolated percentile.

    The method matches the validated exploratory analysis used for the
    canonical PrimeNet performance case study.
    """

    if not values:
        raise ValueError(
            "Percentile requires at least one value."
        )

    if not 0.0 <= probability <= 1.0:
        raise ValueError(
            "Percentile probability must be between 0 and 1."
        )

    ordered = sorted(values)

    position = (
        (len(ordered) - 1)
        * probability
    )

    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return ordered[lower]

    fraction = position - lower

    return (
        ordered[lower]
        + (
            ordered[upper]
            - ordered[lower]
        )
        * fraction
    )


def correlation(
    xs: Sequence[float | int],
    ys: Sequence[float | int],
) -> float:
    """Calculate the Pearson product-moment correlation."""

    if len(xs) != len(ys):
        raise ValueError(
            "Correlation inputs must have equal length."
        )

    if len(xs) < 2:
        raise ValueError(
            "Correlation requires at least two observations."
        )

    mean_x = statistics.mean(xs)
    mean_y = statistics.mean(ys)

    numerator = sum(
        (x - mean_x)
        * (y - mean_y)
        for x, y in zip(xs, ys)
    )

    denominator_x = math.sqrt(
        sum(
            (x - mean_x) ** 2
            for x in xs
        )
    )

    denominator_y = math.sqrt(
        sum(
            (y - mean_y) ** 2
            for y in ys
        )
    )

    denominator = (
        denominator_x
        * denominator_y
    )

    if denominator == 0.0:
        return float("nan")

    return numerator / denominator


def analyze_window(
    rows: Sequence[CensusRow],
    *,
    name: str,
    description: str,
    first_partition: int,
) -> PerformanceWindow:
    """Calculate one transparent full-run or steady-state profile."""

    if first_partition < 1:
        raise ValueError(
            "first_partition must be >= 1."
        )

    selected = [
        row
        for row in rows
        if row.partition >= first_partition
    ]

    if not selected:
        raise ValueError(
            f"No rows selected for window {name!r}."
        )

    runtimes = [
        row.runtime_sec
        for row in selected
    ]

    gap_counts = [
        row.gap_count
        for row in selected
    ]

    twin_counts = [
        row.twin_count
        for row in selected
    ]

    partition_indices = [
        row.partition
        for row in selected
    ]

    partition_rates = [
        row.gap_count
        / row.runtime_sec
        for row in selected
    ]

    total_gaps = sum(gap_counts)
    total_twins = sum(twin_counts)
    total_runtime = sum(runtimes)

    mean_runtime = statistics.mean(
        runtimes
    )

    stddev_runtime = statistics.pstdev(
        runtimes
    )

    runtime_cv = (
        stddev_runtime
        / mean_runtime
    )

    fastest = min(
        selected,
        key=lambda row: row.runtime_sec,
    )

    slowest = max(
        selected,
        key=lambda row: row.runtime_sec,
    )

    return PerformanceWindow(
        name=name,
        description=description,
        first_partition=selected[0].partition,
        last_partition=selected[-1].partition,
        partitions=len(selected),
        total_gaps=total_gaps,
        total_twins=total_twins,
        total_runtime_sec=total_runtime,
        total_runtime_min=(
            total_runtime / 60.0
        ),
        mean_runtime_sec=mean_runtime,
        median_runtime_sec=statistics.median(
            runtimes
        ),
        minimum_runtime_sec=min(runtimes),
        maximum_runtime_sec=max(runtimes),
        runtime_stddev_sec=stddev_runtime,
        runtime_cv=runtime_cv,
        p05_runtime_sec=percentile(
            runtimes,
            0.05,
        ),
        p25_runtime_sec=percentile(
            runtimes,
            0.25,
        ),
        p50_runtime_sec=percentile(
            runtimes,
            0.50,
        ),
        p75_runtime_sec=percentile(
            runtimes,
            0.75,
        ),
        p95_runtime_sec=percentile(
            runtimes,
            0.95,
        ),
        p99_runtime_sec=percentile(
            runtimes,
            0.99,
        ),
        sustained_gaps_per_sec=(
            total_gaps
            / total_runtime
        ),
        sustained_gaps_per_min=(
            total_gaps
            / total_runtime
            * 60.0
        ),
        median_partition_gaps_per_sec=(
            statistics.median(
                partition_rates
            )
        ),
        minimum_partition_gaps_per_sec=min(
            partition_rates
        ),
        maximum_partition_gaps_per_sec=max(
            partition_rates
        ),
        gap_count_runtime_correlation=(
            correlation(
                gap_counts,
                runtimes,
            )
        ),
        partition_index_runtime_correlation=(
            correlation(
                partition_indices,
                runtimes,
            )
        ),
        fastest_partition=fastest.partition,
        fastest_partition_runtime_sec=(
            fastest.runtime_sec
        ),
        fastest_partition_gap_count=(
            fastest.gap_count
        ),
        slowest_partition=slowest.partition,
        slowest_partition_runtime_sec=(
            slowest.runtime_sec
        ),
        slowest_partition_gap_count=(
            slowest.gap_count
        ),
    )


def profile_rows(
    rows: Sequence[CensusRow],
    *,
    count: int,
    from_end: bool,
) -> tuple[dict[str, Any], ...]:
    """Return compact startup or final partition records."""

    if count < 1:
        raise ValueError(
            "Profile count must be positive."
        )

    selected = (
        rows[-count:]
        if from_end
        else rows[:count]
    )

    return tuple(
        {
            "partition": row.partition,
            "range_start": row.range_start,
            "range_end": row.range_end,
            "gap_count": row.gap_count,
            "twin_count": row.twin_count,
            "runtime_sec": row.runtime_sec,
            "gaps_per_sec": (
                row.gap_count
                / row.runtime_sec
            ),
        }
        for row in selected
    )


def build_analysis(
    settings: AnalyzerSettings,
) -> PerformanceAnalysis:
    """Read, validate, and analyze the canonical census."""

    rows = read_census_rows(
        settings.census_csv
    )

    summary = read_census_summary(
        settings.census_summary
    )

    validation_messages = (
        validate_census_contract(
            rows,
            summary,
        )
    )

    windows = (
        analyze_window(
            rows,
            name="full_run",
            description=(
                "Complete execution record, "
                "partitions 1–300."
            ),
            first_partition=1,
        ),
        analyze_window(
            rows,
            name="exclude_first_partition",
            description=(
                "Startup sensitivity profile, "
                "partitions 2–300."
            ),
            first_partition=2,
        ),
        analyze_window(
            rows,
            name="exclude_first_two_partitions",
            description=(
                "Warm-state profile after the first "
                "two startup partitions, "
                "partitions 3–300."
            ),
            first_partition=3,
        ),
        analyze_window(
            rows,
            name="conservative_steady_state",
            description=(
                "Conservative steady-state profile, "
                "partitions 11–300."
            ),
            first_partition=11,
        ),
    )

    csv_runtime = sum(
        row.runtime_sec
        for row in rows
    )

    runtime_difference = (
        summary.runtime_seconds
        - csv_runtime
    )

    runtime_ratio = (
        csv_runtime
        / summary.runtime_seconds
    )

    validation_messages.append(
        "Performance-window analysis completed."
    )

    validation_messages.append(
        "Runtime-accounting comparison completed."
    )

    return PerformanceAnalysis(
        analyzer_version=ANALYZER_VERSION,
        analysis_id=new_analysis_id(),
        generated_at_utc=utc_now_iso(),
        census_csv=str(
            settings.census_csv
        ),
        census_summary=str(
            settings.census_summary
        ),
        canonical_repository=(
            summary.repository
        ),
        census_version=summary.version,
        census_generated_at_utc=(
            summary.generated_at_utc
        ),
        numeric_domain_start=(
            summary.numeric_domain_start
        ),
        numeric_domain_end=(
            summary.numeric_domain_end
        ),
        event_definition=(
            summary.event_definition
        ),
        partitions=len(rows),
        total_gaps=sum(
            row.gap_count
            for row in rows
        ),
        total_twins=sum(
            row.twin_count
            for row in rows
        ),
        global_twin_density=(
            summary.global_twin_density
        ),
        csv_partition_runtime_sec=(
            csv_runtime
        ),
        summary_end_to_end_runtime_sec=(
            summary.runtime_seconds
        ),
        runtime_accounting_difference_sec=(
            runtime_difference
        ),
        runtime_accounting_ratio=(
            runtime_ratio
        ),
        windows=windows,
        startup_profile=profile_rows(
            rows,
            count=10,
            from_end=False,
        ),
        final_profile=profile_rows(
            rows,
            count=10,
            from_end=True,
        ),
        accepted=True,
        validation_messages=tuple(
            validation_messages
        ),
    )


def format_integer(
    value: int,
) -> str:
    return f"{value:,}"


def format_float(
    value: float,
    digits: int = 6,
) -> str:
    if math.isnan(value):
        return "nan"

    return f"{value:.{digits}f}"


def format_window_report(
    window: PerformanceWindow,
) -> list[str]:
    """Format one performance window for the text report."""

    return [
        window.name,
        "-" * len(window.name),
        window.description,
        "",
        (
            "Partition range       : "
            f"{window.first_partition}"
            f"–{window.last_partition}"
        ),
        (
            "Partitions            : "
            f"{format_integer(window.partitions)}"
        ),
        (
            "Total gaps            : "
            f"{format_integer(window.total_gaps)}"
        ),
        (
            "Total twin events     : "
            f"{format_integer(window.total_twins)}"
        ),
        (
            "Total runtime         : "
            f"{format_float(window.total_runtime_sec)} sec"
        ),
        (
            "Total runtime         : "
            f"{format_float(window.total_runtime_min)} min"
        ),
        (
            "Mean runtime          : "
            f"{format_float(window.mean_runtime_sec)} sec"
        ),
        (
            "Median runtime        : "
            f"{format_float(window.median_runtime_sec)} sec"
        ),
        (
            "Minimum runtime       : "
            f"{format_float(window.minimum_runtime_sec)} sec"
        ),
        (
            "Maximum runtime       : "
            f"{format_float(window.maximum_runtime_sec)} sec"
        ),
        (
            "Runtime std. deviation: "
            f"{format_float(window.runtime_stddev_sec)} sec"
        ),
        (
            "Runtime coefficient CV: "
            f"{window.runtime_cv:.6%}"
        ),
        (
            "Runtime P05           : "
            f"{format_float(window.p05_runtime_sec)} sec"
        ),
        (
            "Runtime P25           : "
            f"{format_float(window.p25_runtime_sec)} sec"
        ),
        (
            "Runtime P50           : "
            f"{format_float(window.p50_runtime_sec)} sec"
        ),
        (
            "Runtime P75           : "
            f"{format_float(window.p75_runtime_sec)} sec"
        ),
        (
            "Runtime P95           : "
            f"{format_float(window.p95_runtime_sec)} sec"
        ),
        (
            "Runtime P99           : "
            f"{format_float(window.p99_runtime_sec)} sec"
        ),
        (
            "Sustained gaps/sec    : "
            f"{window.sustained_gaps_per_sec:,.3f}"
        ),
        (
            "Sustained gaps/min    : "
            f"{window.sustained_gaps_per_min:,.3f}"
        ),
        (
            "Median partition rate : "
            f"{window.median_partition_gaps_per_sec:,.3f}"
            " gaps/sec"
        ),
        (
            "Gap/runtime corr.     : "
            f"{window.gap_count_runtime_correlation:.9f}"
        ),
        (
            "Index/runtime corr.   : "
            f"{window.partition_index_runtime_correlation:.9f}"
        ),
        (
            "Fastest partition     : "
            f"{window.fastest_partition} "
            f"({format_float(window.fastest_partition_runtime_sec)} sec)"
        ),
        (
            "Slowest partition     : "
            f"{window.slowest_partition} "
            f"({format_float(window.slowest_partition_runtime_sec)} sec)"
        ),
        "",
    ]


def build_text_report(
    analysis: PerformanceAnalysis,
) -> str:
    """Build the canonical human-readable performance report."""

    lines: list[str] = [
        "PrimeNet Twin-Prime Performance Analysis",
        "========================================",
        "",
        f"Analyzer version: {analysis.analyzer_version}",
        f"Analysis ID: {analysis.analysis_id}",
        f"Generated at UTC: {analysis.generated_at_utc}",
        "",
        "Inputs",
        "------",
        f"Census CSV: {analysis.census_csv}",
        f"Census summary: {analysis.census_summary}",
        (
            "Canonical repository: "
            f"{analysis.canonical_repository}"
        ),
        (
            "Census generated at UTC: "
            f"{analysis.census_generated_at_utc}"
        ),
        "",
        "Scientific domain",
        "-----------------",
        (
            "Numeric domain: "
            f"{format_integer(analysis.numeric_domain_start)}"
            " – "
            f"{format_integer(analysis.numeric_domain_end)}"
        ),
        (
            "Event definition: "
            f"{analysis.event_definition}"
        ),
        (
            "Partitions: "
            f"{format_integer(analysis.partitions)}"
        ),
        (
            "Total gaps: "
            f"{format_integer(analysis.total_gaps)}"
        ),
        (
            "Twin-prime events: "
            f"{format_integer(analysis.total_twins)}"
        ),
        (
            "Global twin density: "
            f"{analysis.global_twin_density:.15f}"
        ),
        "",
        "Runtime accounting",
        "------------------",
        (
            "Partition runtime sum: "
            f"{analysis.csv_partition_runtime_sec:.6f} sec"
        ),
        (
            "End-to-end runtime: "
            f"{analysis.summary_end_to_end_runtime_sec:.6f} sec"
        ),
        (
            "Accounting difference: "
            f"{analysis.runtime_accounting_difference_sec:.6f} sec"
        ),
        (
            "Partition runtime fraction: "
            f"{analysis.runtime_accounting_ratio:.9%}"
        ),
        "",
        "Performance windows",
        "-------------------",
        "",
    ]

    for window in analysis.windows:
        lines.extend(
            format_window_report(window)
        )

    lines.extend(
        (
            "Startup profile",
            "---------------",
        )
    )

    for record in analysis.startup_profile:
        lines.append(
            f"Partition {record['partition']:3d}: "
            f"gaps={record['gap_count']:,}, "
            f"runtime={record['runtime_sec']:.6f} sec, "
            f"rate={record['gaps_per_sec']:,.3f} gaps/sec"
        )

    lines.extend(
        (
            "",
            "Final profile",
            "-------------",
        )
    )

    for record in analysis.final_profile:
        lines.append(
            f"Partition {record['partition']:3d}: "
            f"gaps={record['gap_count']:,}, "
            f"runtime={record['runtime_sec']:.6f} sec, "
            f"rate={record['gaps_per_sec']:,.3f} gaps/sec"
        )

    lines.extend(
        (
            "",
            "Validation",
            "----------",
        )
    )

    for message in analysis.validation_messages:
        lines.append(f"[PASSED] {message}")

    lines.extend(
        (
            "",
            "Accepted: True",
            "",
            (
                "Interpretation: Full-run statistics preserve the "
                "complete execution record. The partitions 3–300 and "
                "11–300 windows provide transparent warm-state and "
                "conservative steady-state profiles without modifying "
                "or discarding the underlying census observations."
            ),
            "",
        )
    )

    return "\n".join(lines)


def atomic_write_text(
    path: Path,
    text: str,
) -> None:
    """Atomically replace a UTF-8 text file."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    descriptor, temporary_name = (
        tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
    )

    temporary_path = Path(
        temporary_name
    )

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            handle.write(text)

            if not text.endswith("\n"):
                handle.write("\n")

            handle.flush()
            os.fsync(handle.fileno())

        os.replace(
            temporary_path,
            path,
        )

    except BaseException:
        try:
            temporary_path.unlink(
                missing_ok=True
            )
        finally:
            raise


def atomic_write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    """Atomically write a formatted UTF-8 JSON document."""

    text = json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    )

    atomic_write_text(
        path,
        text,
    )


def output_actions(
    settings: AnalyzerSettings,
) -> list[tuple[str, Path]]:
    """Return the planned create/replace actions."""

    actions: list[tuple[str, Path]] = []

    for path in (
        settings.analysis_json,
        settings.report_txt,
    ):
        action = (
            "REPLACE"
            if path.exists()
            else "CREATE"
        )

        actions.append(
            (action, path)
        )

    return actions


def validate_output_policy(
    settings: AnalyzerSettings,
) -> None:
    """Protect existing outputs unless overwrite is explicit."""

    existing = [
        path
        for path in (
            settings.analysis_json,
            settings.report_txt,
        )
        if path.exists()
    ]

    if existing and not settings.overwrite:
        formatted = "\n".join(
            f"  {path}"
            for path in existing
        )

        raise FileExistsError(
            "Existing performance-analysis outputs found. "
            "Use --overwrite to replace them atomically.\n"
            f"{formatted}"
        )


def print_window(
    window: PerformanceWindow,
) -> None:
    """Print one concise performance window to the console."""

    print()
    print(window.name)
    print(SUBSEPARATOR)
    print(window.description)
    print(
        f"Partitions             : "
        f"{window.first_partition}"
        f"–{window.last_partition} "
        f"({window.partitions:,})"
    )
    print(
        f"Total gaps             : "
        f"{window.total_gaps:,}"
    )
    print(
        f"Total runtime          : "
        f"{window.total_runtime_sec:.6f} sec"
    )
    print(
        f"Mean runtime           : "
        f"{window.mean_runtime_sec:.6f} sec"
    )
    print(
        f"Median runtime         : "
        f"{window.median_runtime_sec:.6f} sec"
    )
    print(
        f"Runtime std. deviation : "
        f"{window.runtime_stddev_sec:.6f} sec"
    )
    print(
        f"Runtime coefficient CV : "
        f"{window.runtime_cv:.6%}"
    )
    print(
        f"Runtime P95            : "
        f"{window.p95_runtime_sec:.6f} sec"
    )
    print(
        f"Sustained gaps/sec     : "
        f"{window.sustained_gaps_per_sec:,.3f}"
    )
    print(
        f"Gap/runtime correlation: "
        f"{window.gap_count_runtime_correlation:.9f}"
    )


def run_analyzer(
    settings: AnalyzerSettings,
) -> int:
    """Execute validation, analysis, and optional publication."""

    started = time.perf_counter()

    print(SEPARATOR)
    print(
        "PrimeNet Twin-Prime Performance "
        f"Analyzer v{ANALYZER_VERSION}"
    )
    print(SEPARATOR)
    print(
        f"Census CSV      : {settings.census_csv}"
    )
    print(
        f"Census summary  : {settings.census_summary}"
    )
    print(
        f"Analysis JSON   : {settings.analysis_json}"
    )
    print(
        f"Report TXT      : {settings.report_txt}"
    )
    print(
        f"Overwrite       : {settings.overwrite}"
    )
    print(
        f"Dry run         : {settings.dry_run}"
    )
    print(SEPARATOR)

    validate_output_policy(
        settings
    )

    analysis = build_analysis(
        settings
    )

    print()
    print("Validated scientific census")
    print(SUBSEPARATOR)
    print(
        f"Partitions      : {analysis.partitions:,}"
    )
    print(
        f"Total gaps      : {analysis.total_gaps:,}"
    )
    print(
        f"Twin events     : {analysis.total_twins:,}"
    )
    print(
        f"Twin density    : "
        f"{analysis.global_twin_density:.15f}"
    )
    print(
        f"Repository      : "
        f"{analysis.canonical_repository}"
    )

    print()
    print("Runtime accounting")
    print(SUBSEPARATOR)
    print(
        "Partition sum   : "
        f"{analysis.csv_partition_runtime_sec:.6f} sec"
    )
    print(
        "End-to-end      : "
        f"{analysis.summary_end_to_end_runtime_sec:.6f} sec"
    )
    print(
        "Difference      : "
        f"{analysis.runtime_accounting_difference_sec:.6f} sec"
    )
    print(
        "Accounted ratio : "
        f"{analysis.runtime_accounting_ratio:.9%}"
    )

    for window in analysis.windows:
        print_window(window)

    print()
    print("Publication plan")
    print(SUBSEPARATOR)

    for action, path in output_actions(
        settings
    ):
        prefix = (
            "WOULD_"
            if settings.dry_run
            else ""
        )

        print(
            f"{prefix}{action}: {path}"
        )

    if settings.dry_run:
        print()
        print(
            "[DRY RUN] Inputs were validated and "
            "performance statistics were calculated. "
            "No files were created, modified, or deleted."
        )

    else:
        atomic_write_json(
            settings.analysis_json,
            analysis.as_dict(),
        )

        atomic_write_text(
            settings.report_txt,
            build_text_report(analysis),
        )

        print()
        print("[PUBLISHED]")
        print(
            f"JSON report: {settings.analysis_json}"
        )
        print(
            f"Text report: {settings.report_txt}"
        )

    elapsed = (
        time.perf_counter()
        - started
    )

    print()
    print(SEPARATOR)
    print("[ACCEPTED]")
    print(
        "Canonical twin-prime performance "
        "analysis completed successfully."
    )
    print(
        f"Analyzer runtime: {elapsed:.6f} sec"
    )
    print(SEPARATOR)

    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the command-line parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Analyze the accepted PrimeNet 1–3T "
            "Twin Prime Census performance record."
        )
    )

    parser.add_argument(
        "--census-csv",
        type=Path,
        default=DEFAULT_CENSUS_CSV,
        help=(
            "Partition census CSV. Default: "
            f"{DEFAULT_CENSUS_CSV}"
        ),
    )

    parser.add_argument(
        "--census-summary",
        type=Path,
        default=DEFAULT_CENSUS_SUMMARY,
        help=(
            "Accepted census summary JSON. Default: "
            f"{DEFAULT_CENSUS_SUMMARY}"
        ),
    )

    parser.add_argument(
        "--analysis-json",
        type=Path,
        default=DEFAULT_ANALYSIS_JSON,
        help=(
            "Performance-analysis JSON output. Default: "
            f"{DEFAULT_ANALYSIS_JSON}"
        ),
    )

    parser.add_argument(
        "--report-txt",
        type=Path,
        default=DEFAULT_REPORT_TXT,
        help=(
            "Human-readable performance report. Default: "
            f"{DEFAULT_REPORT_TXT}"
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Atomically replace existing analysis outputs."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate inputs and calculate all statistics "
            "without writing output files."
        ),
    )

    return parser


def settings_from_args(
    args: argparse.Namespace,
) -> AnalyzerSettings:
    """Convert command-line arguments into immutable settings."""

    return AnalyzerSettings(
        census_csv=args.census_csv.expanduser(),
        census_summary=(
            args.census_summary.expanduser()
        ),
        analysis_json=(
            args.analysis_json.expanduser()
        ),
        report_txt=(
            args.report_txt.expanduser()
        ),
        overwrite=bool(args.overwrite),
        dry_run=bool(args.dry_run),
    )


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """Command-line entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)
    settings = settings_from_args(args)

    try:
        return run_analyzer(
            settings
        )

    except (
        FileExistsError,
        FileNotFoundError,
        ValueError,
        OSError,
    ) as exc:
        print(
            f"[FAILED] {exc}",
            file=sys.stderr,
        )

        return 2


if __name__ == "__main__":
    raise SystemExit(main())
