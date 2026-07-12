"""
PrimeNet Operational Runtime Summarizer v2.0.0
===============================================

Summarize PrimeNet operational runtime logs without modifying repository
data or certified publication metadata.

Canonical operational inputs
----------------------------
The default summary considers these logs when present:

    prime_range_runtime.csv
        Owned by build_prime_range.py.

    repository_driver_runtime.csv
        Owned by drive_prime_repository.py.

    gap_u16_v3_runtime.csv
        Owned by build_gap_repository.py.

Legacy input
------------
    builder_runtime.csv

The legacy builder log is excluded by default because it contains historical
schemas and mixed production campaigns. It can be included explicitly with:

    --include-legacy

Owned outputs
-------------
This module owns only:

    operational_runtime_summary.json
    operational_runtime_summary.csv

It does not own or modify:

    repository_performance.json
    repository_runtime_summary.json
    repository_runtime_summary.csv
    certified manifests
    release metadata

Safety contract
---------------
- Importing this module has no configuration or file-system side effects.
- Input schemas are interpreted by named headers, never fixed positions.
- Integer values are parsed strictly without float conversion.
- Existing outputs are protected unless --overwrite is explicit.
- Writes are atomic.
- --dry-run performs no writes.
- Missing optional logs are reported but are not fatal when another selected
  source contains usable records.

Examples
--------
    py -m Platform.core.summarize_runtime --dry-run

    py -m Platform.core.summarize_runtime --overwrite

    py -m Platform.core.summarize_runtime \
        --include-legacy \
        --overwrite
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
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from Platform.core.platform_config import (
    PlatformConfiguration,
    load_platform_config,
)


SUMMARIZER_NAME = "PrimeNet Operational Runtime Summarizer"
SUMMARIZER_VERSION = "2.0.0"

DEFAULT_JSON_NAME = "operational_runtime_summary.json"
DEFAULT_CSV_NAME = "operational_runtime_summary.csv"

SOURCE_PRIME_RANGE = "prime_range"
SOURCE_DRIVER = "repository_driver"
SOURCE_GAP = "gap"
SOURCE_LEGACY = "legacy_builder"

CANONICAL_SOURCES = (
    SOURCE_PRIME_RANGE,
    SOURCE_DRIVER,
    SOURCE_GAP,
)

ALL_SOURCES = (
    *CANONICAL_SOURCES,
    SOURCE_LEGACY,
)


@dataclass(frozen=True)
class RuntimePaths:
    repository_root: Path
    logs_dir: Path
    metadata_dir: Path

    prime_range_log: Path
    driver_log: Path
    gap_log: Path
    legacy_builder_log: Path

    summary_json: Path
    summary_csv: Path


@dataclass(frozen=True)
class RuntimeRecord:
    source: str
    source_file: Path
    row_number: int

    timestamp: str
    run_id: str
    action: str
    status: str

    batch_id: int | None
    total_batches: int | None
    range_start: int | None
    range_end: int | None

    runtime_sec: float | None
    runtime_min: float | None

    size_bytes: int | None
    size_gb: float | None

    output_file: str
    message: str

    @property
    def status_normalized(self) -> str:
        return normalize_status(self.status)

    @property
    def successful(self) -> bool:
        return self.status_normalized in {
            "passed",
            "success",
            "completed",
            "ok",
            "inspected",
            "built",
            "skipped",
            "skipped_existing",
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "source_file": str(self.source_file),
            "row_number": self.row_number,
            "timestamp": self.timestamp,
            "run_id": self.run_id,
            "action": self.action,
            "status": self.status,
            "status_normalized": self.status_normalized,
            "successful": self.successful,
            "batch_id": self.batch_id,
            "total_batches": self.total_batches,
            "range_start": self.range_start,
            "range_end": self.range_end,
            "runtime_sec": self.runtime_sec,
            "runtime_min": self.runtime_min,
            "size_bytes": self.size_bytes,
            "size_gb": self.size_gb,
            "output_file": self.output_file,
            "message": self.message,
        }


@dataclass(frozen=True)
class ParseIssue:
    source: str
    source_file: Path
    row_number: int
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "source_file": str(self.source_file),
            "row_number": self.row_number,
            "message": self.message,
        }


@dataclass(frozen=True)
class ParsedSource:
    source: str
    path: Path
    exists: bool
    header: tuple[str, ...]
    records: tuple[RuntimeRecord, ...]
    issues: tuple[ParseIssue, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "path": str(self.path),
            "exists": self.exists,
            "header": list(self.header),
            "record_count": len(self.records),
            "issue_count": len(self.issues),
        }


def now_iso() -> str:
    return datetime.now().isoformat(
        timespec="seconds"
    )


def make_run_id() -> str:
    return (
        datetime.now().strftime("%Y%m%d_%H%M%S")
        + "_"
        + uuid.uuid4().hex[:8]
    )


def resolve_paths(
    config: PlatformConfiguration,
) -> RuntimePaths:
    logs_dir = config.paths.logs_dir
    metadata_dir = config.paths.metadata_dir

    return RuntimePaths(
        repository_root=config.paths.repository_root,
        logs_dir=logs_dir,
        metadata_dir=metadata_dir,
        prime_range_log=(
            logs_dir
            / "prime_range_runtime.csv"
        ),
        driver_log=(
            logs_dir
            / "repository_driver_runtime.csv"
        ),
        gap_log=(
            logs_dir
            / "gap_u16_v3_runtime.csv"
        ),
        legacy_builder_log=(
            logs_dir
            / "builder_runtime.csv"
        ),
        summary_json=(
            metadata_dir
            / DEFAULT_JSON_NAME
        ),
        summary_csv=(
            metadata_dir
            / DEFAULT_CSV_NAME
        ),
    )


def normalize_status(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


def first_text(
    row: Mapping[str, str],
    names: Sequence[str],
    default: str = "",
) -> str:
    for name in names:
        value = row.get(name)

        if value is not None:
            stripped = str(value).strip()

            if stripped:
                return stripped

    return default


def strict_int_text(
    value: str,
    *,
    field: str,
) -> int | None:
    stripped = value.strip()

    if not stripped:
        return None

    signless = (
        stripped[1:]
        if stripped[0] in "+-"
        else stripped
    )

    if not signless.isdigit():
        raise ValueError(
            f"{field} must be an integer, "
            f"found {value!r}"
        )

    return int(stripped)


def first_int(
    row: Mapping[str, str],
    names: Sequence[str],
) -> int | None:
    for name in names:
        value = row.get(name)

        if value is None:
            continue

        if not str(value).strip():
            continue

        return strict_int_text(
            str(value),
            field=name,
        )

    return None


def strict_float_text(
    value: str,
    *,
    field: str,
) -> float | None:
    stripped = value.strip()

    if not stripped:
        return None

    try:
        result = float(stripped)
    except ValueError as exc:
        raise ValueError(
            f"{field} must be numeric, "
            f"found {value!r}"
        ) from exc

    if not math.isfinite(result):
        raise ValueError(
            f"{field} must be finite, "
            f"found {value!r}"
        )

    return result


def first_float(
    row: Mapping[str, str],
    names: Sequence[str],
) -> float | None:
    for name in names:
        value = row.get(name)

        if value is None:
            continue

        if not str(value).strip():
            continue

        return strict_float_text(
            str(value),
            field=name,
        )

    return None


def complete_runtime_values(
    *,
    runtime_sec: float | None,
    runtime_min: float | None,
) -> tuple[
    float | None,
    float | None,
]:
    if (
        runtime_sec is None
        and runtime_min is not None
    ):
        runtime_sec = runtime_min * 60.0

    if (
        runtime_min is None
        and runtime_sec is not None
    ):
        runtime_min = runtime_sec / 60.0

    return runtime_sec, runtime_min


def complete_size_values(
    *,
    size_bytes: int | None,
    size_gb: float | None,
) -> tuple[
    int | None,
    float | None,
]:
    if (
        size_bytes is None
        and size_gb is not None
    ):
        size_bytes = int(
            round(
                size_gb
                * (1024 ** 3)
            )
        )

    if (
        size_gb is None
        and size_bytes is not None
    ):
        size_gb = (
            size_bytes
            / (1024 ** 3)
        )

    return size_bytes, size_gb


def parse_named_record(
    *,
    source: str,
    source_file: Path,
    row_number: int,
    row: Mapping[str, str],
) -> RuntimeRecord:
    runtime_sec = first_float(
        row,
        (
            "total_sec",
            "runtime_sec",
            "runtime_seconds",
            "total_runtime_sec",
            "duration_sec",
        ),
    )
    runtime_min = first_float(
        row,
        (
            "total_min",
            "runtime_min",
            "runtime_minutes",
            "total_runtime_min",
            "duration_min",
        ),
    )

    (
        runtime_sec,
        runtime_min,
    ) = complete_runtime_values(
        runtime_sec=runtime_sec,
        runtime_min=runtime_min,
    )

    if (
        runtime_sec is not None
        and runtime_sec < 0
    ):
        raise ValueError(
            "Runtime seconds must be >= 0."
        )

    if (
        runtime_min is not None
        and runtime_min < 0
    ):
        raise ValueError(
            "Runtime minutes must be >= 0."
        )

    size_bytes = first_int(
        row,
        (
            "size_bytes",
            "file_size_bytes",
            "output_size_bytes",
        ),
    )
    size_gb = first_float(
        row,
        (
            "size_gb",
            "file_size_gb",
            "output_size_gb",
        ),
    )

    (
        size_bytes,
        size_gb,
    ) = complete_size_values(
        size_bytes=size_bytes,
        size_gb=size_gb,
    )

    if (
        size_bytes is not None
        and size_bytes < 0
    ):
        raise ValueError(
            "Size bytes must be >= 0."
        )

    if (
        size_gb is not None
        and size_gb < 0
    ):
        raise ValueError(
            "Size GB must be >= 0."
        )

    status = first_text(
        row,
        (
            "status",
            "result",
        ),
    )

    if not status:
        raise ValueError(
            "Runtime row has no status."
        )

    return RuntimeRecord(
        source=source,
        source_file=source_file,
        row_number=row_number,
        timestamp=first_text(
            row,
            (
                "timestamp",
                "created_at",
                "started_at",
                "completed_at",
            ),
        ),
        run_id=first_text(
            row,
            (
                "run_id",
                "release_id",
            ),
        ),
        action=first_text(
            row,
            (
                "action",
                "operation",
                "mode",
            ),
        ),
        status=status,
        batch_id=first_int(
            row,
            (
                "batch_id",
                "output_batch_index",
                "batch_index",
            ),
        ),
        total_batches=first_int(
            row,
            (
                "total_batches",
                "total_output_batches",
                "batch_count",
            ),
        ),
        range_start=first_int(
            row,
            (
                "range_start",
                "batch_start",
                "start",
            ),
        ),
        range_end=first_int(
            row,
            (
                "range_end",
                "batch_end",
                "end",
            ),
        ),
        runtime_sec=runtime_sec,
        runtime_min=runtime_min,
        size_bytes=size_bytes,
        size_gb=size_gb,
        output_file=first_text(
            row,
            (
                "output_file",
                "file",
                "path",
            ),
        ),
        message=first_text(
            row,
            (
                "message",
                "messages",
                "error",
            ),
        ),
    )


def read_named_csv(
    *,
    source: str,
    path: Path,
) -> ParsedSource:
    if not path.is_file():
        return ParsedSource(
            source=source,
            path=path,
            exists=False,
            header=(),
            records=(),
            issues=(),
        )

    records: list[RuntimeRecord] = []
    issues: list[ParseIssue] = []

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)
        header = tuple(
            reader.fieldnames or ()
        )

        if not header:
            issues.append(
                ParseIssue(
                    source=source,
                    source_file=path,
                    row_number=1,
                    message=(
                        "CSV file has no header."
                    ),
                )
            )

            return ParsedSource(
                source=source,
                path=path,
                exists=True,
                header=header,
                records=(),
                issues=tuple(issues),
            )

        if "status" not in header:
            issues.append(
                ParseIssue(
                    source=source,
                    source_file=path,
                    row_number=1,
                    message=(
                        "CSV header has no "
                        "'status' field."
                    ),
                )
            )

        for row_number, row in enumerate(
            reader,
            start=2,
        ):
            if not any(
                str(value or "").strip()
                for value in row.values()
            ):
                continue

            try:
                records.append(
                    parse_named_record(
                        source=source,
                        source_file=path,
                        row_number=row_number,
                        row=row,
                    )
                )
            except Exception as exc:
                issues.append(
                    ParseIssue(
                        source=source,
                        source_file=path,
                        row_number=row_number,
                        message=(
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        ),
                    )
                )

    return ParsedSource(
        source=source,
        path=path,
        exists=True,
        header=header,
        records=tuple(records),
        issues=tuple(issues),
    )

def read_gap_runtime_csv(
    path: Path,
) -> ParsedSource:
    """
    Read historical and current gap runtime-log schemas.

    Supported schemas:

    Legacy 12-column schema:
        timestamp,batch_id,total_batches,range_start,range_end,
        runtime_sec,runtime_min,file_size_gb,max_gap,boundary_gap,
        terminal_next_prime_computed,status

    Current 14-column schema:
        timestamp,run_id,batch_id,total_batches,range_start,range_end,
        runtime_sec,runtime_min,file_size_gb,max_gap,boundary_gap,
        terminal_next_prime_computed,action,status
    """
    source = SOURCE_GAP

    if not path.is_file():
        return ParsedSource(
            source=source,
            path=path,
            exists=False,
            header=(),
            records=(),
            issues=(),
        )

    records: list[RuntimeRecord] = []
    issues: list[ParseIssue] = []

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.reader(handle)
        header = tuple(next(reader, ()))

        if not header:
            issues.append(
                ParseIssue(
                    source=source,
                    source_file=path,
                    row_number=1,
                    message="CSV file has no header.",
                )
            )

            return ParsedSource(
                source=source,
                path=path,
                exists=True,
                header=header,
                records=(),
                issues=tuple(issues),
            )

        for row_number, raw in enumerate(
            reader,
            start=2,
        ):
            if not raw or not any(
                value.strip()
                for value in raw
            ):
                continue

            try:
                if len(raw) == 12:
                    row = {
                        "timestamp": raw[0],
                        "batch_id": raw[1],
                        "total_batches": raw[2],
                        "range_start": raw[3],
                        "range_end": raw[4],
                        "runtime_sec": raw[5],
                        "runtime_min": raw[6],
                        "file_size_gb": raw[7],
                        "max_gap": raw[8],
                        "boundary_gap": raw[9],
                        "terminal_next_prime_computed": raw[10],
                        "status": raw[11],
                    }

                elif len(raw) == 14:
                    row = {
                        "timestamp": raw[0],
                        "run_id": raw[1],
                        "batch_id": raw[2],
                        "total_batches": raw[3],
                        "range_start": raw[4],
                        "range_end": raw[5],
                        "runtime_sec": raw[6],
                        "runtime_min": raw[7],
                        "file_size_gb": raw[8],
                        "max_gap": raw[9],
                        "boundary_gap": raw[10],
                        "terminal_next_prime_computed": raw[11],
                        "action": raw[12],
                        "status": raw[13],
                    }

                else:
                    raise ValueError(
                        "Unsupported gap runtime row width: "
                        f"{len(raw)} columns"
                    )

                records.append(
                    parse_named_record(
                        source=source,
                        source_file=path,
                        row_number=row_number,
                        row=row,
                    )
                )

            except Exception as exc:
                issues.append(
                    ParseIssue(
                        source=source,
                        source_file=path,
                        row_number=row_number,
                        message=(
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        ),
                    )
                )

    return ParsedSource(
        source=source,
        path=path,
        exists=True,
        header=header,
        records=tuple(records),
        issues=tuple(issues),
    )

def source_paths(
    paths: RuntimePaths,
) -> dict[str, Path]:
    return {
        SOURCE_PRIME_RANGE: (
            paths.prime_range_log
        ),
        SOURCE_DRIVER: (
            paths.driver_log
        ),
        SOURCE_GAP: (
            paths.gap_log
        ),
        SOURCE_LEGACY: (
            paths.legacy_builder_log
        ),
    }


def selected_sources(
    *,
    requested: Sequence[str],
    include_legacy: bool,
) -> tuple[str, ...]:
    if requested:
        result = list(
            dict.fromkeys(requested)
        )
    else:
        result = list(
            CANONICAL_SOURCES
        )

    if (
        include_legacy
        and SOURCE_LEGACY
        not in result
    ):
        result.append(
            SOURCE_LEGACY
        )

    return tuple(result)


def safe_mean(
    values: Sequence[float],
) -> float | None:
    if not values:
        return None

    return statistics.mean(values)


def safe_median(
    values: Sequence[float],
) -> float | None:
    if not values:
        return None

    return statistics.median(values)


def safe_stdev(
    values: Sequence[float],
) -> float | None:
    if not values:
        return None

    if len(values) == 1:
        return 0.0

    return statistics.stdev(values)


def numeric_summary(
    values: Sequence[float],
) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "sum": None,
            "mean": None,
            "median": None,
            "minimum": None,
            "maximum": None,
            "stdev": None,
        }

    return {
        "count": len(values),
        "sum": sum(values),
        "mean": safe_mean(values),
        "median": safe_median(values),
        "minimum": min(values),
        "maximum": max(values),
        "stdev": safe_stdev(values),
    }


def record_reference(
    record: RuntimeRecord | None,
) -> dict[str, Any] | None:
    if record is None:
        return None

    return record.as_dict()


def summarize_records(
    records: Sequence[RuntimeRecord],
) -> dict[str, Any]:
    statuses = Counter(
        record.status_normalized
        for record in records
    )
    actions = Counter(
        (
            normalize_status(record.action)
            if record.action
            else ""
        )
        for record in records
    )

    successful = [
        record
        for record in records
        if record.successful
    ]
    unsuccessful = [
        record
        for record in records
        if not record.successful
    ]

    successful_runtime_rows = [
        record
        for record in successful
        if record.runtime_min is not None
    ]

    runtime_minutes = [
        float(record.runtime_min)
        for record
        in successful_runtime_rows
        if record.runtime_min is not None
    ]
    runtime_seconds = [
        float(record.runtime_sec)
        for record
        in successful_runtime_rows
        if record.runtime_sec is not None
    ]
    sizes_gb = [
        float(record.size_gb)
        for record in successful
        if record.size_gb is not None
    ]
    sizes_bytes = [
        int(record.size_bytes)
        for record in successful
        if record.size_bytes is not None
    ]

    fastest = (
        min(
            successful_runtime_rows,
            key=lambda record: (
                float(record.runtime_min)
            ),
        )
        if successful_runtime_rows
        else None
    )
    slowest = (
        max(
            successful_runtime_rows,
            key=lambda record: (
                float(record.runtime_min)
            ),
        )
        if successful_runtime_rows
        else None
    )

    return {
        "record_count": len(records),
        "successful_count": (
            len(successful)
        ),
        "unsuccessful_count": (
            len(unsuccessful)
        ),
        "status_counts": dict(
            sorted(statuses.items())
        ),
        "action_counts": {
            key: value
            for key, value
            in sorted(actions.items())
            if key
        },
        "runtime_minutes": (
            numeric_summary(
                runtime_minutes
            )
        ),
        "runtime_seconds": (
            numeric_summary(
                runtime_seconds
            )
        ),
        "size_gb": (
            numeric_summary(
                sizes_gb
            )
        ),
        "size_bytes": {
            **numeric_summary(
                [
                    float(value)
                    for value in sizes_bytes
                ]
            ),
            "sum_integer": (
                sum(sizes_bytes)
                if sizes_bytes
                else None
            ),
        },
        "fastest_successful_record": (
            record_reference(fastest)
        ),
        "slowest_successful_record": (
            record_reference(slowest)
        ),
    }


def build_summary(
    *,
    run_id: str,
    paths: RuntimePaths,
    selected: Sequence[str],
    parsed_sources: Sequence[
        ParsedSource
    ],
) -> dict[str, Any]:
    all_records = [
        record
        for parsed in parsed_sources
        for record in parsed.records
    ]
    all_issues = [
        issue
        for parsed in parsed_sources
        for issue in parsed.issues
    ]

    by_source: dict[str, Any] = {}

    for parsed in parsed_sources:
        by_source[parsed.source] = {
            **parsed.as_dict(),
            "summary": summarize_records(
                parsed.records
            ),
            "issues": [
                issue.as_dict()
                for issue in parsed.issues
            ],
        }

    return {
        "summary_type": (
            "PrimeNet operational runtime summary"
        ),
        "summarizer_version": (
            SUMMARIZER_VERSION
        ),
        "run_id": run_id,
        "created_at": now_iso(),
        "repository_root": str(
            paths.repository_root
        ),
        "logs_dir": str(
            paths.logs_dir
        ),
        "metadata_dir": str(
            paths.metadata_dir
        ),
        "selected_sources": list(
            selected
        ),
        "source_count": len(
            parsed_sources
        ),
        "existing_source_count": sum(
            parsed.exists
            for parsed in parsed_sources
        ),
        "missing_sources": [
            {
                "source": parsed.source,
                "path": str(parsed.path),
            }
            for parsed in parsed_sources
            if not parsed.exists
        ],
        "parse_issue_count": len(
            all_issues
        ),
        "overall": summarize_records(
            all_records
        ),
        "sources": by_source,
    }


def flatten_summary_metrics(
    summary: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(
        scope: str,
        metric: str,
        value: Any,
    ) -> None:
        if isinstance(
            value,
            (dict, list),
        ):
            rendered = json.dumps(
                value,
                sort_keys=True,
            )
        elif value is None:
            rendered = ""
        else:
            rendered = value

        rows.append(
            {
                "scope": scope,
                "metric": metric,
                "value": rendered,
            }
        )

    add(
        "summary",
        "summarizer_version",
        summary.get(
            "summarizer_version"
        ),
    )
    add(
        "summary",
        "run_id",
        summary.get("run_id"),
    )
    add(
        "summary",
        "created_at",
        summary.get("created_at"),
    )
    add(
        "summary",
        "selected_sources",
        summary.get(
            "selected_sources"
        ),
    )
    add(
        "summary",
        "existing_source_count",
        summary.get(
            "existing_source_count"
        ),
    )
    add(
        "summary",
        "parse_issue_count",
        summary.get(
            "parse_issue_count"
        ),
    )

    overall = summary.get(
        "overall",
        {},
    )

    if isinstance(overall, Mapping):
        for key, value in overall.items():
            add(
                "overall",
                str(key),
                value,
            )

    sources = summary.get(
        "sources",
        {},
    )

    if isinstance(sources, Mapping):
        for source, payload in (
            sources.items()
        ):
            if not isinstance(
                payload,
                Mapping,
            ):
                continue

            for key in (
                "path",
                "exists",
                "record_count",
                "issue_count",
            ):
                add(
                    f"source:{source}",
                    key,
                    payload.get(key),
                )

            source_summary = payload.get(
                "summary",
                {},
            )

            if isinstance(
                source_summary,
                Mapping,
            ):
                for key, value in (
                    source_summary.items()
                ):
                    add(
                        f"source:{source}",
                        str(key),
                        value,
                    )

    return rows


def atomic_write_text(
    path: Path,
    text: str,
) -> None:
    if not path.parent.is_dir():
        raise FileNotFoundError(
            "Output directory does not "
            f"exist: {path.parent}"
        )

    file_descriptor, temporary_name = (
        tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
    )
    temporary = Path(
        temporary_name
    )

    try:
        with os.fdopen(
            file_descriptor,
            "w",
            encoding="utf-8",
            newline="",
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


def atomic_write_csv(
    path: Path,
    rows: Iterable[
        Mapping[str, Any]
    ],
) -> None:
    if not path.parent.is_dir():
        raise FileNotFoundError(
            "Output directory does not "
            f"exist: {path.parent}"
        )

    file_descriptor, temporary_name = (
        tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
    )
    temporary = Path(
        temporary_name
    )

    try:
        with os.fdopen(
            file_descriptor,
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=(
                    "scope",
                    "metric",
                    "value",
                ),
            )
            writer.writeheader()

            for row in rows:
                writer.writerow(row)

            handle.flush()
            os.fsync(handle.fileno())

        os.replace(
            temporary,
            path,
        )

    finally:
        if temporary.exists():
            temporary.unlink()


def print_source_report(
    parsed: ParsedSource,
) -> None:
    print(
        f"{parsed.source:20s} : "
        f"{parsed.path}"
    )
    print(
        f"{'':20s}   "
        f"exists={parsed.exists}, "
        f"records={len(parsed.records)}, "
        f"issues={len(parsed.issues)}"
    )


def run_summarizer(
    *,
    selected: Sequence[str],
    overwrite: bool,
    dry_run: bool,
) -> int:
    config = load_platform_config()
    paths = resolve_paths(config)
    run_id = make_run_id()

    mapping = source_paths(paths)

    parsed_sources: list[ParsedSource] = []

    for source in selected:
        path = mapping[source]

        if source == SOURCE_GAP:
            parsed = read_gap_runtime_csv(path)
        else:
            parsed = read_named_csv(
                source=source,
                path=path,
            )

        parsed_sources.append(parsed)

    total_records = sum(
        len(parsed.records)
        for parsed in parsed_sources
    )

    if total_records == 0:
        raise RuntimeError(
            "No usable runtime records were "
            "found in the selected sources."
        )

    summary = build_summary(
        run_id=run_id,
        paths=paths,
        selected=selected,
        parsed_sources=parsed_sources,
    )

    output_paths = (
        paths.summary_json,
        paths.summary_csv,
    )
    existing_outputs = [
        path
        for path in output_paths
        if path.exists()
    ]

    if (
        existing_outputs
        and not overwrite
        and not dry_run
    ):
        rendered = "\n  ".join(
            str(path)
            for path in existing_outputs
        )

        raise FileExistsError(
            "Operational runtime summary "
            "outputs already exist. Use "
            "--overwrite to replace them:\n"
            f"  {rendered}"
        )

    print("=" * 80)
    print(
        f"{SUMMARIZER_NAME} "
        f"v{SUMMARIZER_VERSION}"
    )
    print("=" * 80)
    print(
        f"Run ID          : {run_id}"
    )
    print(
        f"Repository root : "
        f"{paths.repository_root}"
    )
    print(
        f"Logs directory  : "
        f"{paths.logs_dir}"
    )
    print(
        f"Metadata dir    : "
        f"{paths.metadata_dir}"
    )
    print(
        f"Selected sources: "
        f"{', '.join(selected)}"
    )
    print(
        f"Overwrite       : {overwrite}"
    )
    print(
        f"Dry run         : {dry_run}"
    )
    print("=" * 80)

    print()
    print("Input sources")
    print("-" * 80)

    for parsed in parsed_sources:
        print_source_report(parsed)

    overall = summary["overall"]

    print()
    print("Operational summary")
    print("-" * 80)
    print(
        f"Records         : "
        f"{overall['record_count']}"
    )
    print(
        f"Successful      : "
        f"{overall['successful_count']}"
    )
    print(
        f"Unsuccessful    : "
        f"{overall['unsuccessful_count']}"
    )
    print(
        f"Parse issues    : "
        f"{summary['parse_issue_count']}"
    )
    print(
        f"Status counts   : "
        f"{overall['status_counts']}"
    )

    runtime_metrics = (
        overall["runtime_minutes"]
    )

    if runtime_metrics["count"]:
        print(
            "Runtime rows    : "
            f"{runtime_metrics['count']}"
        )
        print(
            "Runtime sum     : "
            f"{runtime_metrics['sum']:.6f} min"
        )
        print(
            "Runtime mean    : "
            f"{runtime_metrics['mean']:.6f} min"
        )
        print(
            "Runtime median  : "
            f"{runtime_metrics['median']:.6f} min"
        )
        print(
            "Runtime minimum : "
            f"{runtime_metrics['minimum']:.6f} min"
        )
        print(
            "Runtime maximum : "
            f"{runtime_metrics['maximum']:.6f} min"
        )

    print()
    print("Output plan")
    print("-" * 80)
    print(
        f"JSON : {paths.summary_json}"
    )
    print(
        f"CSV  : {paths.summary_csv}"
    )

    if dry_run:
        print()
        print(
            "[DRY RUN] No files were "
            "created, modified, or deleted."
        )
        print("=" * 80)
        return 0

    atomic_write_text(
        paths.summary_json,
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    atomic_write_csv(
        paths.summary_csv,
        flatten_summary_metrics(
            summary
        ),
    )

    print()
    print(
        f"[SAVED] {paths.summary_json}"
    )
    print(
        f"[SAVED] {paths.summary_csv}"
    )
    print(
        "[UNCHANGED] Certified and legacy "
        "publication artifacts were not modified."
    )
    print("=" * 80)

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize PrimeNet operational "
            "runtime logs."
        )
    )

    parser.add_argument(
        "--source",
        action="append",
        choices=ALL_SOURCES,
        default=[],
        help=(
            "Select a runtime source. May be "
            "specified more than once. Defaults "
            "to all canonical sources."
        ),
    )

    parser.add_argument(
        "--include-legacy",
        action="store_true",
        help=(
            "Also include legacy "
            "builder_runtime.csv."
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Atomically replace existing "
            "operational summary outputs."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Read and summarize inputs without "
            "writing output files."
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        selected = selected_sources(
            requested=args.source,
            include_legacy=(
                args.include_legacy
            ),
        )

        return run_summarizer(
            selected=selected,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
        )

    except (
        FileExistsError,
        FileNotFoundError,
        RuntimeError,
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