"""
PrimeNet Index-Coordinate Query API v2.0.0
==========================================

Canonical scientific query access to the PrimeNet repository.

Coordinate system
-----------------
PrimeNet uses the one-based prime index as its canonical coordinate:

    p(i) = i-th stored prime
    g(i) = p(i + 1) - p(i)

The canonical left-owned gap repository stores one outgoing gap for
every stored prime, including the final stored prime. Therefore:

    valid prime indices: 1 .. total_primes
    valid gap indices:   1 .. total_primes

The final stored gap uses the independently computed next prime beyond
the physical prime repository extent.

Architectural role
------------------
This module is the scientific/index-coordinate layer.

It composes:

    Platform.core.repository.PrimeRepository
    Platform.core.repository.GapRepository

The physical repository layer owns:

    - file discovery;
    - numeric ordering;
    - range adjacency;
    - configured paths;
    - physical storage contracts.

This query layer owns:

    - global one-based prime-index coordinates;
    - p(i) and g(i);
    - cross-partition windows;
    - floor and ceiling prime queries;
    - numeric and index partition lookup;
    - bounded read-only array caching.

This module does not:

    - parse manifests;
    - discover repository files independently;
    - write files;
    - modify arrays;
    - certify repository arithmetic;
    - publish metadata.

Examples
--------
    from Platform.core.query_repository import (
        PrimeQueryRepository,
    )

    repository = PrimeQueryRepository()

    print(repository.prime(1))
    print(repository.gap(1))
    print(repository.primes(1_000_000, 10))
    print(repository.gaps(1_000_000, 10))

Direct execution
----------------
    py -m Platform.core.query_repository
"""

from __future__ import annotations

import bisect
import sys
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, TypeVar

import numpy as np

from Platform.core.repository import (
    GAP_DTYPE,
    PRIME_DTYPE,
    GapRepository as PhysicalGapRepository,
    PrimeRepository as PhysicalPrimeRepository,
)


API_NAME = "PrimeNet Index-Coordinate Query API"
API_VERSION = "2.0.0"


@dataclass(frozen=True)
class QueryPartition:
    """
    One aligned prime/gap partition in global index coordinates.
    """

    index: int
    range_start: int
    range_end: int

    prime_count: int
    gap_count: int

    first_prime_index: int
    last_prime_index: int

    prime_path: Path
    gap_path: Path

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "range_start": self.range_start,
            "range_end": self.range_end,
            "prime_count": self.prime_count,
            "gap_count": self.gap_count,
            "first_prime_index": (
                self.first_prime_index
            ),
            "last_prime_index": (
                self.last_prime_index
            ),
            "prime_path": self.prime_path,
            "gap_path": self.gap_path,
        }


ArrayType = TypeVar(
    "ArrayType",
    bound=np.ndarray,
)


class _ArrayCache(Generic[ArrayType]):
    """
    Small least-recently-used cache of read-only memory-mapped arrays.
    """

    def __init__(
        self,
        capacity: int,
    ) -> None:
        if isinstance(capacity, bool):
            raise TypeError(
                "Cache capacity must be an integer."
            )

        if capacity <= 0:
            raise ValueError(
                "Cache capacity must be > 0."
            )

        self.capacity = capacity
        self._arrays: OrderedDict[
            int,
            ArrayType,
        ] = OrderedDict()

    def get(
        self,
        key: int,
    ) -> ArrayType | None:
        array = self._arrays.pop(
            key,
            None,
        )

        if array is not None:
            self._arrays[key] = array

        return array

    def put(
        self,
        key: int,
        array: ArrayType,
    ) -> None:
        existing = self._arrays.pop(
            key,
            None,
        )

        if (
            existing is not None
            and existing is not array
        ):
            self._close_array(existing)

        self._arrays[key] = array

        while (
            len(self._arrays)
            > self.capacity
        ):
            _, evicted = (
                self._arrays.popitem(
                    last=False
                )
            )
            self._close_array(evicted)

    def clear(self) -> None:
        while self._arrays:
            _, array = (
                self._arrays.popitem(
                    last=False
                )
            )
            self._close_array(array)

    @staticmethod
    def _close_array(
        array: np.ndarray,
    ) -> None:
        memory_map = getattr(
            array,
            "_mmap",
            None,
        )

        if memory_map is not None:
            try:
                memory_map.close()
            except Exception:
                pass

    def __len__(self) -> int:
        return len(self._arrays)


def _load_read_only_array(
    path: Path,
    *,
    expected_dtype: np.dtype,
    repository_label: str,
) -> np.ndarray:
    """
    Load one already-discovered repository array for indexed access.

    Physical discovery and topology are owned by repository.py.
    This helper performs a bounded, read-only mmap for fast queries.
    """
    array = np.load(
        path,
        mmap_mode="r",
        allow_pickle=False,
    )

    if array.ndim != 1:
        raise ValueError(
            f"{repository_label} array is not 1D: "
            f"{path.name} shape={array.shape}"
        )

    if array.shape[0] == 0:
        raise ValueError(
            f"{repository_label} array is empty: "
            f"{path.name}"
        )

    if array.dtype != expected_dtype:
        raise ValueError(
            f"{repository_label} array has invalid dtype: "
            f"{path.name} dtype={array.dtype}, "
            f"expected={expected_dtype}"
        )

    if array.flags.writeable:
        raise ValueError(
            f"{repository_label} array unexpectedly "
            f"opened writable: {path.name}"
        )

    return array


def _read_array_count(
    path: Path,
    *,
    expected_dtype: np.dtype,
    repository_label: str,
) -> int:
    """
    Read one array's validated shape without scanning its values.
    """
    array = _load_read_only_array(
        path,
        expected_dtype=expected_dtype,
        repository_label=repository_label,
    )

    try:
        return int(array.shape[0])
    finally:
        memory_map = getattr(
            array,
            "_mmap",
            None,
        )

        if memory_map is not None:
            try:
                memory_map.close()
            except Exception:
                pass


class PrimeQueryRepository:
    """
    Canonical PrimeNet scientific/index-coordinate query interface.

    Public API
    ----------
    summary()
    partition_for_n(n)
    partition_index_for_n(n)
    partition_for_index(i)
    partition_record_for_index(i)
    prime(i)
    gap(i)
    primes(i, length)
    gaps(i, length)
    floor_prime(n)
    ceiling_prime(n)
    contains_prime(n)
    gap_after_prime_index(i)
    clear_cache()
    close()
    """

    def __init__(
        self,
        repository_root: (
            str | Path | None
        ) = None,
        cache_size: int = 4,
    ) -> None:
        if isinstance(cache_size, bool):
            raise TypeError(
                "cache_size must be an integer."
            )

        if cache_size <= 0:
            raise ValueError(
                "cache_size must be > 0."
            )

        self.cache_size = cache_size

        self.prime_repository = (
            PhysicalPrimeRepository(
                repository_root
            )
        )
        self.gap_repository = (
            PhysicalGapRepository(
                repository_root
            )
        )

        self.repository_root = (
            self.prime_repository
            .repository_root
        )
        self.root = self.repository_root

        self.prime_dir = (
            self.prime_repository
            .data_dir
        )
        self.gap_dir = (
            self.gap_repository
            .data_dir
        )
        self.metadata_dir = (
            self.prime_repository
            .metadata_dir
        )

        self._validate_repository_roots()
        self._validate_physical_topology()

        self._prime_cache = _ArrayCache[
            np.ndarray
        ](cache_size)
        self._gap_cache = _ArrayCache[
            np.ndarray
        ](cache_size)

        self._query_partitions = (
            self._build_query_partitions()
        )

        if not self._query_partitions:
            raise RuntimeError(
                "No aligned PrimeNet query "
                "partitions were created."
            )

        self._range_starts = [
            item.range_start
            for item in self._query_partitions
        ]
        self._range_ends = [
            item.range_end
            for item in self._query_partitions
        ]

        self._cumulative_offsets = [
            item.first_prime_index - 1
            for item in self._query_partitions
        ]

        self.total_primes = sum(
            item.prime_count
            for item in self._query_partitions
        )
        self.total_gaps = sum(
            item.gap_count
            for item in self._query_partitions
        )

        if (
            self.total_primes
            != self.total_gaps
        ):
            raise ValueError(
                "Global prime/gap count mismatch: "
                f"primes={self.total_primes}, "
                f"gaps={self.total_gaps}"
            )

        self.range_start = (
            self._query_partitions[0]
            .range_start
        )
        self.range_end = (
            self._query_partitions[-1]
            .range_end
        )

        # Compatibility views for existing exploratory code.
        # These are generated from the validated physical repositories,
        # not from manifests.
        self.partitions = [
            {
                "index": item.index,
                "range_start": (
                    item.range_start
                ),
                "range_end": (
                    item.range_end
                ),
                "path": (
                    item.prime_path
                ),
                "prime_count": (
                    item.prime_count
                ),
                "first_prime_index": (
                    item.first_prime_index
                ),
                "last_prime_index": (
                    item.last_prime_index
                ),
            }
            for item in self._query_partitions
        ]

        self.gap_partitions = [
            {
                "index": item.index,
                "range_start": (
                    item.range_start
                ),
                "range_end": (
                    item.range_end
                ),
                "path": (
                    item.gap_path
                ),
                "gap_count": (
                    item.gap_count
                ),
                "first_prime_index": (
                    item.first_prime_index
                ),
                "last_prime_index": (
                    item.last_prime_index
                ),
            }
            for item in self._query_partitions
        ]

        self.range_starts = list(
            self._range_starts
        )
        self.range_ends = list(
            self._range_ends
        )
        self.prime_counts = [
            item.prime_count
            for item in self._query_partitions
        ]
        self.cumulative_counts = list(
            self._cumulative_offsets
        )

    def _validate_repository_roots(
        self,
    ) -> None:
        if (
            self.prime_repository
            .repository_root
            != self.gap_repository
            .repository_root
        ):
            raise ValueError(
                "Prime and gap repositories "
                "have different roots."
            )

    def _validate_physical_topology(
        self,
    ) -> None:
        prime_ranges = (
            self.prime_repository
            .range_files()
        )
        gap_ranges = (
            self.gap_repository
            .range_files()
        )

        if len(prime_ranges) != len(
            gap_ranges
        ):
            raise ValueError(
                "Prime/gap partition-count "
                "mismatch: "
                f"primes={len(prime_ranges)}, "
                f"gaps={len(gap_ranges)}"
            )

        for index, (
            prime_range,
            gap_range,
        ) in enumerate(
            zip(
                prime_ranges,
                gap_ranges,
            )
        ):
            prime_key = (
                prime_range.start,
                prime_range.end,
            )
            gap_key = (
                gap_range.start,
                gap_range.end,
            )

            if prime_key != gap_key:
                raise ValueError(
                    "Prime/gap topology mismatch "
                    f"at partition {index}: "
                    f"prime={prime_key}, "
                    f"gap={gap_key}"
                )

    def _build_query_partitions(
        self,
    ) -> list[QueryPartition]:
        prime_ranges = (
            self.prime_repository
            .range_files()
        )
        gap_ranges = (
            self.gap_repository
            .range_files()
        )

        partitions: list[
            QueryPartition
        ] = []

        cumulative_count = 0

        for index, (
            prime_range,
            gap_range,
        ) in enumerate(
            zip(
                prime_ranges,
                gap_ranges,
            )
        ):
            prime_count = (
                _read_array_count(
                    prime_range.path,
                    expected_dtype=PRIME_DTYPE,
                    repository_label="Prime",
                )
            )
            gap_count = (
                _read_array_count(
                    gap_range.path,
                    expected_dtype=GAP_DTYPE,
                    repository_label="Gap",
                )
            )

            if prime_count != gap_count:
                raise ValueError(
                    "Prime/gap count mismatch "
                    f"at partition {index} "
                    f"({prime_range.start}-"
                    f"{prime_range.end}): "
                    f"primes={prime_count}, "
                    f"gaps={gap_count}"
                )

            first_index = (
                cumulative_count + 1
            )
            last_index = (
                cumulative_count
                + prime_count
            )

            partitions.append(
                QueryPartition(
                    index=index,
                    range_start=(
                        prime_range.start
                    ),
                    range_end=(
                        prime_range.end
                    ),
                    prime_count=prime_count,
                    gap_count=gap_count,
                    first_prime_index=(
                        first_index
                    ),
                    last_prime_index=(
                        last_index
                    ),
                    prime_path=(
                        prime_range.path
                    ),
                    gap_path=(
                        gap_range.path
                    ),
                )
            )

            cumulative_count = (
                last_index
            )

        return partitions

    def query_partitions(
        self,
    ) -> list[QueryPartition]:
        """
        Return validated query partitions in canonical order.
        """
        return list(
            self._query_partitions
        )

    def clear_cache(self) -> None:
        """
        Close and remove all internally cached memory maps.
        """
        self._prime_cache.clear()
        self._gap_cache.clear()

    def close(self) -> None:
        """
        Release cached memory-mapped arrays.
        """
        self.clear_cache()

    def __enter__(
        self,
    ) -> "PrimeQueryRepository":
        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        self.close()

    def _prime_array(
        self,
        partition_index: int,
    ) -> np.ndarray:
        cached = self._prime_cache.get(
            partition_index
        )

        if cached is not None:
            return cached

        partition = (
            self._query_partitions[
                partition_index
            ]
        )
        array = _load_read_only_array(
            partition.prime_path,
            expected_dtype=PRIME_DTYPE,
            repository_label="Prime",
        )
        self._prime_cache.put(
            partition_index,
            array,
        )

        return array

    def _gap_array(
        self,
        partition_index: int,
    ) -> np.ndarray:
        cached = self._gap_cache.get(
            partition_index
        )

        if cached is not None:
            return cached

        partition = (
            self._query_partitions[
                partition_index
            ]
        )
        array = _load_read_only_array(
            partition.gap_path,
            expected_dtype=GAP_DTYPE,
            repository_label="Gap",
        )
        self._gap_cache.put(
            partition_index,
            array,
        )

        return array

    @staticmethod
    def _validate_integer(
        value: int,
        *,
        name: str,
    ) -> int:
        if isinstance(value, bool):
            raise TypeError(
                f"{name} must be an integer."
            )

        if not isinstance(
            value,
            (int, np.integer),
        ):
            raise TypeError(
                f"{name} must be an integer."
            )

        return int(value)

    @staticmethod
    def _validate_length(
        length: int,
    ) -> int:
        validated = (
            PrimeQueryRepository
            ._validate_integer(
                length,
                name="length",
            )
        )

        if validated < 0:
            raise ValueError(
                "length must be >= 0."
            )

        return validated

    def summary(
        self,
    ) -> dict[str, Any]:
        return {
            "api_version": API_VERSION,
            "root": str(
                self.repository_root
            ),
            "prime_dir": str(
                self.prime_dir
            ),
            "gap_dir": str(
                self.gap_dir
            ),
            "prime_partitions": len(
                self._query_partitions
            ),
            "gap_partitions": len(
                self._query_partitions
            ),
            "total_primes": (
                self.total_primes
            ),
            "total_gaps": (
                self.total_gaps
            ),
            "range_start": (
                self.range_start
            ),
            "range_end": (
                self.range_end
            ),
            "prime_dtype": str(
                PRIME_DTYPE
            ),
            "gap_dtype": str(
                GAP_DTYPE
            ),
            "cache_size": (
                self.cache_size
            ),
            "left_owned_full_gaps": True,
            "final_gap_available": True,
            "read_only": True,
        }

    def partition_index_for_n(
        self,
        n: int,
    ) -> int:
        n = self._validate_integer(
            n,
            name="n",
        )

        index = (
            bisect.bisect_right(
                self._range_starts,
                n,
            )
            - 1
        )

        if (
            index < 0
            or n
            > self._range_ends[index]
        ):
            raise ValueError(
                f"n={n} is outside the "
                "repository numeric extent "
                f"{self.range_start}.."
                f"{self.range_end}."
            )

        return index

    def partition_for_n(
        self,
        n: int,
    ) -> QueryPartition:
        """
        Return the numeric-range partition containing n.
        """
        return self._query_partitions[
            self.partition_index_for_n(n)
        ]

    def partition_for_index(
        self,
        i: int,
    ) -> tuple[int, int]:
        """
        Map one-based global prime index i to:

            (
                zero-based partition index,
                zero-based local index,
            )
        """
        i = self._validate_integer(
            i,
            name="i",
        )

        if (
            i < 1
            or i > self.total_primes
        ):
            raise ValueError(
                f"prime index i={i} is "
                "outside the repository "
                f"coordinate extent "
                f"1..{self.total_primes}."
            )

        zero_based_index = i - 1

        partition_index = (
            bisect.bisect_right(
                self._cumulative_offsets,
                zero_based_index,
            )
            - 1
        )

        local_index = (
            zero_based_index
            - self._cumulative_offsets[
                partition_index
            ]
        )

        return (
            partition_index,
            local_index,
        )

    def partition_record_for_index(
        self,
        i: int,
    ) -> QueryPartition:
        partition_index, _ = (
            self.partition_for_index(i)
        )

        return self._query_partitions[
            partition_index
        ]

    def prime(
        self,
        i: int,
    ) -> int:
        partition_index, local_index = (
            self.partition_for_index(i)
        )

        array = self._prime_array(
            partition_index
        )

        return int(
            array[local_index]
        )

    def gap(
        self,
        i: int,
    ) -> int:
        """
        Return the left-owned outgoing gap g(i).

        The final valid coordinate is i=total_primes.
        """
        partition_index, local_index = (
            self.partition_for_index(i)
        )

        array = self._gap_array(
            partition_index
        )

        if local_index >= array.shape[0]:
            raise ValueError(
                f"No gap is available for "
                f"prime index i={i}."
            )

        return int(
            array[local_index]
        )

    def primes(
        self,
        i: int,
        length: int,
    ) -> np.ndarray:
        i = self._validate_integer(
            i,
            name="i",
        )
        length = self._validate_length(
            length
        )

        if length == 0:
            return np.empty(
                0,
                dtype=PRIME_DTYPE,
            )

        if i < 1:
            raise ValueError(
                "i must be >= 1."
            )

        final_index = (
            i + length - 1
        )

        if final_index > self.total_primes:
            raise ValueError(
                "Prime window exceeds "
                "repository coordinate extent: "
                f"requested {i}..{final_index}, "
                f"available 1..{self.total_primes}."
            )

        result = np.empty(
            length,
            dtype=PRIME_DTYPE,
        )

        written = 0
        current_index = i

        while written < length:
            (
                partition_index,
                local_index,
            ) = self.partition_for_index(
                current_index
            )

            array = self._prime_array(
                partition_index
            )

            take = min(
                length - written,
                int(array.shape[0])
                - local_index,
            )

            if take <= 0:
                raise RuntimeError(
                    "Prime window traversal "
                    "made no progress."
                )

            result[
                written:
                written + take
            ] = array[
                local_index:
                local_index + take
            ]

            written += take
            current_index += take

        return result

    def gaps(
        self,
        i: int,
        length: int,
    ) -> np.ndarray:
        i = self._validate_integer(
            i,
            name="i",
        )
        length = self._validate_length(
            length
        )

        if length == 0:
            return np.empty(
                0,
                dtype=GAP_DTYPE,
            )

        if i < 1:
            raise ValueError(
                "i must be >= 1."
            )

        final_index = (
            i + length - 1
        )

        if final_index > self.total_gaps:
            raise ValueError(
                "Gap window exceeds "
                "repository coordinate extent: "
                f"requested {i}..{final_index}, "
                f"available 1..{self.total_gaps}."
            )

        result = np.empty(
            length,
            dtype=GAP_DTYPE,
        )

        written = 0
        current_index = i

        while written < length:
            (
                partition_index,
                local_index,
            ) = self.partition_for_index(
                current_index
            )

            array = self._gap_array(
                partition_index
            )

            take = min(
                length - written,
                int(array.shape[0])
                - local_index,
            )

            if take <= 0:
                raise RuntimeError(
                    "Gap window traversal "
                    "made no progress."
                )

            result[
                written:
                written + take
            ] = array[
                local_index:
                local_index + take
            ]

            written += take
            current_index += take

        return result

    def floor_prime(
        self,
        n: int,
    ) -> int | None:
        """
        Return the greatest stored prime <= n.

        For n above the repository numeric extent, the final stored
        prime is returned. For n below the first repository range,
        None is returned.
        """
        n = self._validate_integer(
            n,
            name="n",
        )

        if n < self.range_start:
            return None

        if n > self.range_end:
            partition_index = (
                len(
                    self._query_partitions
                )
                - 1
            )
        else:
            partition_index = (
                self.partition_index_for_n(n)
            )

        array = self._prime_array(
            partition_index
        )

        position = (
            int(
                np.searchsorted(
                    array,
                    n,
                    side="right",
                )
            )
            - 1
        )

        if position >= 0:
            return int(
                array[position]
            )

        if partition_index == 0:
            return None

        previous = self._prime_array(
            partition_index - 1
        )
        return int(
            previous[-1]
        )

    def ceiling_prime(
        self,
        n: int,
    ) -> int | None:
        """
        Return the smallest stored prime >= n.

        For n below the repository numeric extent, the first stored
        prime is returned. For n above the repository extent, None is
        returned.
        """
        n = self._validate_integer(
            n,
            name="n",
        )

        if n > self.range_end:
            return None

        if n < self.range_start:
            partition_index = 0
        else:
            partition_index = (
                self.partition_index_for_n(n)
            )

        array = self._prime_array(
            partition_index
        )

        position = int(
            np.searchsorted(
                array,
                n,
                side="left",
            )
        )

        if position < array.shape[0]:
            return int(
                array[position]
            )

        if (
            partition_index + 1
            >= len(
                self._query_partitions
            )
        ):
            return None

        following = self._prime_array(
            partition_index + 1
        )
        return int(
            following[0]
        )

    def contains_prime(
        self,
        n: int,
    ) -> bool:
        n = self._validate_integer(
            n,
            name="n",
        )

        return (
            self.floor_prime(n)
            == n
        )

    def gap_after_prime_index(
        self,
        i: int,
    ) -> int:
        return self.gap(i)


# Temporary compatibility alias.
#
# Existing code that imports:
#
#     from Platform.core.query_repository import PrimeRepository
#
# will continue to work until downstream modules are migrated to the
# clearer PrimeQueryRepository name.
PrimeRepository = PrimeQueryRepository


def main() -> int:
    try:
        with PrimeQueryRepository() as repository:
            print("=" * 80)
            print(
                f"{API_NAME} "
                f"v{API_VERSION}"
            )
            print("=" * 80)

            print(
                repository.summary()
            )

            print()
            print("Sample scalar queries")
            print("-" * 80)

            for index in (
                1,
                2,
                3,
                10,
                1_000_000,
            ):
                print(
                    f"p({index}) = "
                    f"{repository.prime(index)}"
                )

            for index in (
                1,
                2,
                3,
                10,
                1_000_000,
            ):
                print(
                    f"g({index}) = "
                    f"{repository.gap(index)}"
                )

            numeric_sample = (
                repository.range_start
            )

            print()
            print("Numeric queries")
            print("-" * 80)
            print(
                f"floor_prime("
                f"{numeric_sample}) = "
                f"{repository.floor_prime(numeric_sample)}"
            )
            print(
                f"ceiling_prime("
                f"{numeric_sample}) = "
                f"{repository.ceiling_prime(numeric_sample)}"
            )
            print(
                f"contains_prime("
                f"{numeric_sample}) = "
                f"{repository.contains_prime(numeric_sample)}"
            )

            print()
            print("Window sample")
            print("-" * 80)

            prime_window = (
                repository.primes(
                    1_000_000,
                    10,
                )
            )
            gap_window = (
                repository.gaps(
                    1_000_000,
                    10,
                )
            )

            print(
                "primes:",
                prime_window,
            )
            print(
                "gaps:  ",
                gap_window,
            )

            print()
            print("Final gap coordinate")
            print("-" * 80)
            print(
                f"g({repository.total_gaps}) = "
                f"{repository.gap(repository.total_gaps)}"
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