from pathlib import Path
from dataclasses import dataclass


@dataclass(frozen=True)
class RangeFile:
    path: Path
    kind: str
    start: int
    end: int


def parse_range_file(path: Path, prefix: str) -> RangeFile:
    """
    Parse files like:
        primes_1_10000000000.npy
        gaps_1_10000000000.npy

    Repository order is numeric order, not lexical order.
    """
    stem = path.stem

    if not stem.startswith(prefix + "_"):
        raise ValueError(f"Unexpected file prefix: {path.name}")

    body = stem[len(prefix) + 1 :]
    parts = body.split("_")

    if len(parts) != 2:
        raise ValueError(f"Invalid range filename: {path.name}")

    start = int(parts[0])
    end = int(parts[1])

    if start > end:
        raise ValueError(f"Invalid numeric range: {path.name}")

    return RangeFile(
        path=path,
        kind=prefix,
        start=start,
        end=end,
    )


def sorted_range_files(directory: Path, prefix: str):
    """
    Return range files sorted by mathematical coordinate.

    Important:
    Do NOT sort repository files alphabetically.
    """
    files = [
        parse_range_file(path, prefix)
        for path in directory.glob(f"{prefix}_*.npy")
    ]

    return sorted(files, key=lambda rf: (rf.start, rf.end))


def validate_adjacency(range_files):
    """
    Validate that range files are strictly increasing and non-overlapping.
    Allows PrimeNet's normal convention:

        previous.end + 1 == next.start
    """
    issues = []

    for prev, curr in zip(range_files, range_files[1:]):
        expected = prev.end + 1

        if curr.start != expected:
            issues.append(
                {
                    "previous": prev.path.name,
                    "current": curr.path.name,
                    "previous_end": prev.end,
                    "current_start": curr.start,
                    "expected_start": expected,
                }
            )

    return issues