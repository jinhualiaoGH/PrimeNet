"""
PrimeNet Physical Repository API v2.0.0
=======================================

Canonical read-only physical access to PrimeNet repository partitions.

This module provides two parallel storage-layer APIs:

    PrimeRepository
        Canonical uint64 prime partitions.

    GapRepository
        Canonical left-owned uint16 gap partitions.

Architectural role
------------------
This module owns physical repository access only.

It answers questions such as:

    - Which canonical range files exist?
    - Are their numeric ranges adjacent?
    - Can a partition be safely loaded read-only?
    - Does its dtype, shape, and physical range satisfy the contract?
    - Can blocks be streamed in canonical numeric order?

It does not:

    - read repository manifests;
    - define global prime-index coordinates;
    - answer p(i) or g(i);
    - perform scientific observations;
    - modify repository files;
    - write metadata or logs.

Higher-level index-coordinate queries belong in:

    Platform.core.query_repository

Design principles
-----------------
1. Physical files are the authoritative storage input.
2. Repository files are ordered numerically, never lexically.
3. Array access is strictly read-only.
4. Pickled NumPy payloads are never permitted.
5. Prime arrays must be one-dimensional uint64.
6. Gap arrays must be one-dimensional uint16.
7. Range topology must be canonically adjacent.
8. Importing this module has no configuration or file-system side effects.

Examples
--------
    from Platform.core.repository import (
        PrimeRepository,
        GapRepository,
    )

    primes = PrimeRepository()
    first_prime_block = primes.load_block(0)

    gaps = GapRepository()
    first_gap_block = gaps.load_block(0)

Direct execution
----------------
    py -m Platform.core.repository
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Generic, Iterator, TypeVar
import sys

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


API_NAME = "PrimeNet Physical Repository API"
API_VERSION = "2.0.0"

PRIME_DTYPE = np.dtype(np.uint64)
GAP_DTYPE = np.dtype(np.uint16)


@dataclass(frozen=True)
class RepositoryLayout:
    """
    Resolved physical repository layout.
    """

    repository_root: Path
    ranges_dir: Path
    gaps_dir: Path
    metadata_dir: Path
    logs_dir: Path


@dataclass(frozen=True)
class PrimeBlock:
    """
    One validated, read-only prime repository partition.
    """

    index: int
    path: Path
    start: int
    end: int
    count: int
    min_prime: int
    max_prime: int
    primes: np.ndarray


@dataclass(frozen=True)
class GapBlock:
    """
    One validated, read-only gap repository partition.
    """

    index: int
    path: Path
    start: int
    end: int
    count: int
    min_gap: int
    max_gap: int
    gaps: np.ndarray


BlockType = TypeVar(
    "BlockType",
    PrimeBlock,
    GapBlock,
)


def _resolve_layout(
    repository_root: Path | str | None,
) -> tuple[
    PlatformConfiguration,
    RepositoryLayout,
]:
    """
    Resolve configured or custom repository paths lazily.

    Importing this module does not call load_platform_config().
    Configuration is loaded only when a repository object is created.
    """
    config = load_platform_config()
    configured_paths = config.paths

    if repository_root is None:
        root = (
            configured_paths.repository_root
            .expanduser()
            .resolve()
        )

        layout = RepositoryLayout(
            repository_root=root,
            ranges_dir=(
                configured_paths.ranges_dir
                .expanduser()
                .resolve()
            ),
            gaps_dir=(
                configured_paths.gaps_dir
                .expanduser()
                .resolve()
            ),
            metadata_dir=(
                configured_paths.metadata_dir
                .expanduser()
                .resolve()
            ),
            logs_dir=(
                configured_paths.logs_dir
                .expanduser()
                .resolve()
            ),
        )

        return config, layout

    root = (
        Path(repository_root)
        .expanduser()
        .resolve()
    )

    # Preserve configured directory names without retaining the
    # configured absolute repository root.
    ranges_name = configured_paths.ranges_dir.name
    gaps_name = configured_paths.gaps_dir.name
    metadata_name = configured_paths.metadata_dir.name
    logs_name = configured_paths.logs_dir.name

    layout = RepositoryLayout(
        repository_root=root,
        ranges_dir=root / ranges_name,
        gaps_dir=root / gaps_name,
        metadata_dir=root / metadata_name,
        logs_dir=root / logs_name,
    )

    return config, layout


class _ReadOnlyRangeRepository(
    Generic[BlockType]
):
    """
    Shared physical repository behavior.

    Subclasses define:
        - directory;
        - filename kind;
        - exact dtype;
        - block construction;
        - array-specific validation.
    """

    repository_label = "repository"
    file_kind = ""
    expected_dtype = np.dtype(np.uint8)

    def __init__(
        self,
        repository_root: Path | str | None = None,
    ) -> None:
        (
            self.config,
            self.layout,
        ) = _resolve_layout(
            repository_root
        )

        self.repository_root = (
            self.layout.repository_root
        )
        self.metadata_dir = (
            self.layout.metadata_dir
        )
        self.logs_dir = (
            self.layout.logs_dir
        )

        self.data_dir = (
            self._resolve_data_dir()
        )

        if not self.data_dir.is_dir():
            raise FileNotFoundError(
                f"{self.repository_label.capitalize()} "
                f"directory not found: {self.data_dir}"
            )

        self._range_files = (
            sorted_range_files(
                self.data_dir,
                self.file_kind,
            )
        )

        if not self._range_files:
            raise RuntimeError(
                f"No {self.repository_label} range "
                f"files found in {self.data_dir}"
            )

        adjacency_issues = (
            validate_adjacency(
                self._range_files
            )
        )

        if adjacency_issues:
            raise ValueError(
                f"{self.repository_label.capitalize()} "
                "range files are not canonically "
                f"adjacent: {adjacency_issues[0]}"
            )

        self._validate_unique_ranges()

        self._files = [
            range_file.path
            for range_file in self._range_files
        ]

        self._range_starts = [
            range_file.start
            for range_file in self._range_files
        ]
        self._range_ends = [
            range_file.end
            for range_file in self._range_files
        ]

    def _resolve_data_dir(self) -> Path:
        raise NotImplementedError

    def _validate_unique_ranges(self) -> None:
        seen: set[tuple[int, int]] = set()

        for range_file in self._range_files:
            key = (
                range_file.start,
                range_file.end,
            )

            if key in seen:
                raise ValueError(
                    "Duplicate physical repository "
                    f"range: {key}"
                )

            seen.add(key)

    @classmethod
    def _load_array(
        cls,
        path: Path,
        mmap_mode: str = "r",
    ) -> np.ndarray:
        """
        Load one canonical array strictly read-only.
        """
        if mmap_mode != "r":
            raise ValueError(
                f"{cls.__name__} only permits "
                "mmap_mode='r'."
            )

        array = np.load(
            path,
            mmap_mode="r",
            allow_pickle=False,
        )

        if array.ndim != 1:
            raise ValueError(
                f"{cls.repository_label.capitalize()} "
                f"array is not 1D: "
                f"{path.name} shape={array.shape}"
            )

        if array.shape[0] == 0:
            raise ValueError(
                f"{cls.repository_label.capitalize()} "
                f"array is empty: {path.name}"
            )

        if array.dtype != cls.expected_dtype:
            raise ValueError(
                f"{cls.repository_label.capitalize()} "
                "array has invalid dtype: "
                f"{path.name} dtype={array.dtype}, "
                f"expected={cls.expected_dtype}"
            )

        return array

    def _validate_array_contract(
        self,
        range_file: RangeFile,
        array: np.ndarray,
    ) -> None:
        raise NotImplementedError

    def _make_block(
        self,
        index: int,
        range_file: RangeFile,
        array: np.ndarray,
    ) -> BlockType:
        raise NotImplementedError

    def block_count(self) -> int:
        """
        Return the number of physical partitions.
        """
        return len(self._range_files)

    def files(self) -> list[Path]:
        """
        Return physical files in canonical numeric order.
        """
        return list(self._files)

    def range_files(self) -> list[RangeFile]:
        """
        Return parsed range-file records in canonical order.
        """
        return list(self._range_files)

    def range_starts(self) -> list[int]:
        return list(self._range_starts)

    def range_ends(self) -> list[int]:
        return list(self._range_ends)

    def first_range(self) -> RangeFile:
        return self._range_files[0]

    def last_range(self) -> RangeFile:
        return self._range_files[-1]

    def load_block(
        self,
        index: int,
        mmap_mode: str = "r",
    ) -> BlockType:
        """
        Load and validate one partition by zero-based index.
        """
        if isinstance(index, bool):
            raise TypeError(
                "Block index must be an integer."
            )

        if index < 0 or index >= len(
            self._range_files
        ):
            raise IndexError(
                f"Block index out of range: {index}"
            )

        range_file = (
            self._range_files[index]
        )

        array = self._load_array(
            range_file.path,
            mmap_mode=mmap_mode,
        )

        self._validate_array_contract(
            range_file,
            array,
        )

        return self._make_block(
            index,
            range_file,
            array,
        )

    def iter_blocks(
        self,
        mmap_mode: str = "r",
    ) -> Iterator[BlockType]:
        """
        Stream validated partitions in canonical numeric order.
        """
        for index in range(
            len(self._range_files)
        ):
            yield self.load_block(
                index,
                mmap_mode=mmap_mode,
            )

    def total_items_fast(self) -> int:
        """
        Count stored elements from validated NumPy shapes.

        This reads array headers through read-only mmap but does not
        scan all array values.
        """
        total = 0

        for index in range(
            len(self._range_files)
        ):
            block = self.load_block(index)
            total += block.count

        return total

    def boundaries(
        self,
    ) -> list[
        tuple[int, int, int, int]
    ]:
        """
        Return canonical physical partition boundaries.

        Each tuple contains:

            (
                zero_based_block_index,
                numeric_range_start,
                numeric_range_end,
                stored_element_count,
            )
        """
        rows: list[
            tuple[int, int, int, int]
        ] = []

        for index in range(
            len(self._range_files)
        ):
            block = self.load_block(index)

            rows.append(
                (
                    index,
                    block.start,
                    block.end,
                    block.count,
                )
            )

        return rows

    def summary(
        self,
    ) -> dict[str, object]:
        """
        Return a lightweight physical repository summary.
        """
        first = self.load_block(0)
        last = self.load_block(
            len(self._range_files) - 1
        )

        return {
            "api_version": API_VERSION,
            "repository_type": (
                self.repository_label
            ),
            "repository_root": str(
                self.repository_root
            ),
            "data_dir": str(
                self.data_dir
            ),
            "metadata_dir": str(
                self.metadata_dir
            ),
            "block_count": (
                self.block_count()
            ),
            "first_file": (
                first.path.name
            ),
            "last_file": (
                last.path.name
            ),
            "range_start": (
                first.start
            ),
            "range_end": (
                last.end
            ),
            "dtype": str(
                self.expected_dtype
            ),
            "read_only": True,
        }


class PrimeRepository(
    _ReadOnlyRangeRepository[PrimeBlock]
):
    """
    Canonical read-only physical prime repository.

    This class owns physical prime partition discovery and validation.
    It does not define the global p(i) coordinate system.
    """

    repository_label = "prime"
    file_kind = "primes"
    expected_dtype = PRIME_DTYPE

    def _resolve_data_dir(self) -> Path:
        self.ranges_dir = (
            self.layout.ranges_dir
        )
        return self.ranges_dir

    def _validate_array_contract(
        self,
        range_file: RangeFile,
        array: np.ndarray,
    ) -> None:
        min_prime = int(array[0])
        max_prime = int(array[-1])

        if min_prime < max(
            2,
            range_file.start,
        ):
            raise ValueError(
                "Prime below filename range in "
                f"{range_file.path.name}: "
                f"{min_prime} < "
                f"{max(2, range_file.start)}"
            )

        if max_prime > range_file.end:
            raise ValueError(
                "Prime above filename range in "
                f"{range_file.path.name}: "
                f"{max_prime} > "
                f"{range_file.end}"
            )

        if min_prime > max_prime:
            raise ValueError(
                "Prime block endpoints are "
                "reversed in "
                f"{range_file.path.name}: "
                f"{min_prime} > {max_prime}"
            )

    def _make_block(
        self,
        index: int,
        range_file: RangeFile,
        array: np.ndarray,
    ) -> PrimeBlock:
        return PrimeBlock(
            index=index,
            path=range_file.path,
            start=range_file.start,
            end=range_file.end,
            count=int(array.shape[0]),
            min_prime=int(array[0]),
            max_prime=int(array[-1]),
            primes=array,
        )

    def iter_primes(
        self,
    ) -> Iterator[int]:
        """
        Stream all stored primes one by one.

        Block-level iteration is preferred for large computations.
        """
        for block in self.iter_blocks():
            for prime in block.primes:
                yield int(prime)

    def total_primes_fast(self) -> int:
        """
        Return total stored prime count.
        """
        return self.total_items_fast()

    def summary(
        self,
    ) -> dict[str, object]:
        result = super().summary()

        first = self.load_block(0)
        last = self.load_block(
            self.block_count() - 1
        )

        result.update(
            {
                "min_prime": (
                    first.min_prime
                ),
                "max_prime": (
                    last.max_prime
                ),
            }
        )

        return result


class GapRepository(
    _ReadOnlyRangeRepository[GapBlock]
):
    """
    Canonical read-only physical gap repository.

    Contract:
        - one-dimensional uint16 arrays;
        - one physical gap partition per canonical numeric range;
        - every stored gap must be strictly positive.

    Prime/gap count correspondence and g(i) arithmetic are verified by
    Platform.core.verify_gap_repository and composed by the future
    PrimeQueryRepository.
    """

    repository_label = "gap"
    file_kind = "gaps"
    expected_dtype = GAP_DTYPE

    def _resolve_data_dir(self) -> Path:
        self.gaps_dir = (
            self.layout.gaps_dir
        )
        return self.gaps_dir

    def _validate_array_contract(
        self,
        range_file: RangeFile,
        array: np.ndarray,
    ) -> None:
        min_gap = int(array.min())
        max_gap = int(array.max())

        if min_gap <= 0:
            raise ValueError(
                "Gap array contains a nonpositive "
                f"value in {range_file.path.name}: "
                f"min_gap={min_gap}"
            )

        if max_gap > np.iinfo(
            np.uint16
        ).max:
            raise ValueError(
                "Gap array exceeds uint16 capacity "
                f"in {range_file.path.name}: "
                f"max_gap={max_gap}"
            )

    def _make_block(
        self,
        index: int,
        range_file: RangeFile,
        array: np.ndarray,
    ) -> GapBlock:
        return GapBlock(
            index=index,
            path=range_file.path,
            start=range_file.start,
            end=range_file.end,
            count=int(array.shape[0]),
            min_gap=int(array.min()),
            max_gap=int(array.max()),
            gaps=array,
        )

    def iter_gaps(
        self,
    ) -> Iterator[int]:
        """
        Stream all stored gaps one by one.

        Block-level iteration is preferred for large computations.
        """
        for block in self.iter_blocks():
            for gap in block.gaps:
                yield int(gap)

    def total_gaps_fast(self) -> int:
        """
        Return total stored gap count.
        """
        return self.total_items_fast()

    def summary(
        self,
    ) -> dict[str, object]:
        result = super().summary()

        first = self.load_block(0)
        last = self.load_block(
            self.block_count() - 1
        )

        result.update(
            {
                "first_block_min_gap": (
                    first.min_gap
                ),
                "first_block_max_gap": (
                    first.max_gap
                ),
                "last_block_min_gap": (
                    last.min_gap
                ),
                "last_block_max_gap": (
                    last.max_gap
                ),
            }
        )

        return result


def _print_summary(
    title: str,
    summary: dict[str, object],
) -> None:
    print(title)
    print("-" * 80)

    for key, value in summary.items():
        print(f"{key}: {value}")


def main() -> int:
    try:
        print("=" * 80)
        print(
            f"{API_NAME} v{API_VERSION}"
        )
        print("=" * 80)

        prime_repository = (
            PrimeRepository()
        )
        gap_repository = (
            GapRepository()
        )

        _print_summary(
            "Prime repository",
            prime_repository.summary(),
        )

        print()

        _print_summary(
            "Gap repository",
            gap_repository.summary(),
        )

        print()
        print("First 3 prime blocks")
        print("-" * 80)

        for block in islice(
            prime_repository.iter_blocks(),
            3,
        ):
            print(
                f"[{block.index:03d}] "
                f"{block.path.name} | "
                f"count={block.count:,} | "
                f"min={block.min_prime:,} | "
                f"max={block.max_prime:,}"
            )

        print()
        print("First 3 gap blocks")
        print("-" * 80)

        for block in islice(
            gap_repository.iter_blocks(),
            3,
        ):
            print(
                f"[{block.index:03d}] "
                f"{block.path.name} | "
                f"count={block.count:,} | "
                f"min_gap={block.min_gap:,} | "
                f"max_gap={block.max_gap:,}"
            )

        print()
        print(
            "Physical Repository API "
            "loaded successfully."
        )
        print("=" * 80)

        return 0

    except (
        FileNotFoundError,
        IndexError,
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