"""
PrimeNet Range File Utilities v1.1.0

Canonical parsing, numeric ordering, and adjacency validation for
PrimeNet repository range files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class RangeFile:
    path: Path
    kind: str
    start: int
    end: int


def parse_range_file(
    path: Path | str,
    prefix: str,
) -> RangeFile:
    """
    Parse a canonical PrimeNet range filename.

    Examples:
        primes_1_10000000000.npy
        gaps_1_10000000000.npy

    Repository order is numeric order, not lexical order.
    """
    path = Path(path)

    if not prefix or "_" in prefix:
        raise ValueError(
            f"Invalid range-file prefix: {prefix!r}"
        )

    if path.suffix != ".npy":
        raise ValueError(
            f"Range file must use the .npy extension: {path.name}"
        )

    stem = path.stem
    expected_prefix = f"{prefix}_"

    if not stem.startswith(expected_prefix):
        raise ValueError(
            f"Unexpected file prefix: {path.name}"
        )

    body = stem[len(expected_prefix):]
    parts = body.split("_")

    if len(parts) != 2:
        raise ValueError(
            f"Invalid range filename: {path.name}"
        )

    try:
        start = int(parts[0])
        end = int(parts[1])
    except ValueError as exc:
        raise ValueError(
            f"Invalid numeric coordinates in range filename: {path.name}"
        ) from exc

    if start < 1:
        raise ValueError(
            f"Range start must be >= 1: {path.name}"
        )

    if end < start:
        raise ValueError(
            f"Range end must be >= range start: {path.name}"
        )

    return RangeFile(
        path=path,
        kind=prefix,
        start=start,
        end=end,
    )


def sorted_range_files(
    directory: Path | str,
    prefix: str,
) -> list[RangeFile]:
    """
    Return canonical range files sorted by mathematical coordinate.

    Important:
        Repository files must never be sorted alphabetically.
    """
    directory = Path(directory)

    files = [
        parse_range_file(path, prefix)
        for path in directory.glob(f"{prefix}_*.npy")
    ]

    return sorted(
        files,
        key=lambda range_file: (
            range_file.start,
            range_file.end,
        ),
    )


def validate_adjacency(
    range_files: Sequence[RangeFile],
) -> list[dict[str, object]]:
    """
    Validate canonical adjacency between ordered range files.

    PrimeNet's normal convention is:

        previous.end + 1 == current.start

    Returns one issue record for every detected gap or overlap.
    """
    issues: list[dict[str, object]] = []

    for previous, current in zip(
        range_files,
        range_files[1:],
    ):
        expected_start = previous.end + 1

        if current.start == expected_start:
            continue

        issue_type = (
            "GAP"
            if current.start > expected_start
            else "OVERLAP"
        )

        issues.append(
            {
                "issue_type": issue_type,
                "previous": previous.path.name,
                "current": current.path.name,
                "previous_end": previous.end,
                "current_start": current.start,
                "expected_start": expected_start,
            }
        )

    return issues
