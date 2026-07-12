"""
PrimeNet Query Repository Contract Test v2.0.0
==============================================

Deterministic acceptance tests for the canonical PrimeNet index-coordinate
query API.

This module validates the public scientific access contract exposed by:

    Platform.core.query_repository.PrimeQueryRepository

The test suite covers:

    - repository initialization and summary metadata;
    - compatibility alias behavior;
    - scalar prime coordinates p(i);
    - scalar gap coordinates g(i);
    - prime partition boundaries;
    - cross-partition prime windows;
    - cross-partition gap windows;
    - the final left-owned gap coordinate;
    - floor-prime queries;
    - ceiling-prime queries;
    - prime-membership queries;
    - zero-length windows;
    - invalid scalar coordinates;
    - invalid window coordinates;
    - context-manager behavior;
    - cache cleanup;
    - representative window timings.

Repository law
--------------

Prime coordinates are one-based:

    p(1) = 2

Gap coordinates are left-owned:

    g(i) = p(i + 1) - p(i)

Every stored prime owns one outgoing gap, including the final stored prime.
The final gap therefore uses the terminal successor prime computed during
canonical gap construction.

This module is read-only. It must never create, modify, replace, or delete
repository artifacts.

Run:

    cd C:\\PrimeNet
    py -m Platform.core.query_window_test

Exit codes:

    0
        All contract tests passed.

    1
        One or more contract tests failed.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Callable

import numpy as np

from Platform.core.query_repository import (
    PrimeQueryRepository,
    PrimeRepository,
)


TEST_VERSION = "2.0.0"

SEPARATOR = "=" * 80
SUBSEPARATOR = "-" * 80


@dataclass(frozen=True)
class TestResult:
    """
    Result of one deterministic contract test.
    """

    name: str
    passed: bool
    runtime_sec: float
    message: str = ""


class ContractTestFailure(AssertionError):
    """
    Raised when a PrimeNet query contract assertion fails.
    """


def require(condition: bool, message: str) -> None:
    """
    Require a contract condition to be true.
    """

    if not condition:
        raise ContractTestFailure(message)


def require_equal(
    actual: object,
    expected: object,
    message: str,
) -> None:
    """
    Require two scalar values to be equal.
    """

    if actual != expected:
        raise ContractTestFailure(
            f"{message}: expected={expected!r}, actual={actual!r}"
        )


def require_array_equal(
    actual: np.ndarray,
    expected: np.ndarray,
    message: str,
) -> None:
    """
    Require two NumPy arrays to be exactly equal.
    """

    if not np.array_equal(actual, expected):
        raise ContractTestFailure(
            f"{message}: arrays are not equal."
        )


def require_raises(
    exception_type: type[BaseException],
    function: Callable[[], object],
    message: str,
) -> BaseException:
    """
    Require a callable to raise the expected exception type.
    """

    try:
        function()
    except exception_type as exc:
        return exc
    except Exception as exc:
        raise ContractTestFailure(
            f"{message}: expected {exception_type.__name__}, "
            f"received {type(exc).__name__}: {exc}"
        ) from exc

    raise ContractTestFailure(
        f"{message}: expected {exception_type.__name__}, "
        "but no exception was raised."
    )


def run_test(
    name: str,
    function: Callable[[], None],
) -> TestResult:
    """
    Execute one contract test and capture its result.
    """

    started = time.perf_counter()

    try:
        function()
    except Exception as exc:
        runtime_sec = time.perf_counter() - started
        return TestResult(
            name=name,
            passed=False,
            runtime_sec=runtime_sec,
            message=f"{type(exc).__name__}: {exc}",
        )

    runtime_sec = time.perf_counter() - started

    return TestResult(
        name=name,
        passed=True,
        runtime_sec=runtime_sec,
    )


def test_initialization_and_summary() -> None:
    """
    Validate repository initialization and summary metadata.
    """

    with PrimeQueryRepository() as repo:
        summary = repo.summary()

        require_equal(
            summary["api_version"],
            "2.0.0",
            "Unexpected query API version",
        )
        require_equal(
            summary["prime_partitions"],
            len(repo.partitions),
            "Prime partition count mismatch",
        )
        require_equal(
            summary["gap_partitions"],
            len(repo.gap_partitions),
            "Gap partition count mismatch",
        )
        require_equal(
            summary["total_primes"],
            repo.total_primes,
            "Total prime count mismatch",
        )
        require_equal(
            summary["total_gaps"],
            repo.total_gaps,
            "Total gap count mismatch",
        )
        require_equal(
            summary["prime_dtype"],
            "uint64",
            "Unexpected prime dtype",
        )
        require_equal(
            summary["gap_dtype"],
            "uint16",
            "Unexpected gap dtype",
        )
        require(
            bool(summary["left_owned_full_gaps"]),
            "Repository does not report full left-owned gaps.",
        )
        require(
            bool(summary["final_gap_available"]),
            "Repository does not report the final gap as available.",
        )
        require(
            bool(summary["read_only"]),
            "Query repository does not report read-only access.",
        )
        require(
            repo.total_primes > 0,
            "Repository contains no prime coordinates.",
        )
        require_equal(
            repo.total_gaps,
            repo.total_primes,
            "Full left-owned gap count must equal prime count",
        )


def test_compatibility_alias() -> None:
    """
    Validate the legacy PrimeRepository compatibility alias.
    """

    require(
        PrimeRepository is PrimeQueryRepository,
        "PrimeRepository compatibility alias is not identical "
        "to PrimeQueryRepository.",
    )

    with PrimeRepository() as repo:
        require(
            len(repo.partitions) > 0,
            "Compatibility alias initialized an empty repository.",
        )


def test_basic_scalar_coordinates() -> None:
    """
    Validate known scalar prime and gap coordinates.
    """

    with PrimeQueryRepository() as repo:
        require_equal(
            repo.prime(1),
            2,
            "p(1) mismatch",
        )
        require_equal(
            repo.prime(2),
            3,
            "p(2) mismatch",
        )
        require_equal(
            repo.prime(3),
            5,
            "p(3) mismatch",
        )
        require_equal(
            repo.prime(10),
            29,
            "p(10) mismatch",
        )
        require_equal(
            repo.prime(1_000_000),
            15_485_863,
            "p(1,000,000) mismatch",
        )

        require_equal(
            repo.gap(1),
            1,
            "g(1) mismatch",
        )
        require_equal(
            repo.gap(2),
            2,
            "g(2) mismatch",
        )
        require_equal(
            repo.gap(3),
            2,
            "g(3) mismatch",
        )
        require_equal(
            repo.gap(10),
            2,
            "g(10) mismatch",
        )
        require_equal(
            repo.gap(1_000_000),
            4,
            "g(1,000,000) mismatch",
        )


def test_first_partition_boundary() -> None:
    """
    Validate the first cross-partition left-owned gap.
    """

    with PrimeQueryRepository() as repo:
        boundary_i = int(
            repo.partitions[0]["last_prime_index"]
        )

        left_prime = repo.prime(boundary_i)
        right_prime = repo.prime(boundary_i + 1)
        boundary_gap = repo.gap(boundary_i)

        require_equal(
            boundary_gap,
            right_prime - left_prime,
            "First partition boundary gap mismatch",
        )


def test_cross_partition_windows() -> None:
    """
    Validate prime and gap windows spanning a partition boundary.
    """

    with PrimeQueryRepository() as repo:
        boundary_i = int(
            repo.partitions[0]["last_prime_index"]
        )
        start_i = boundary_i - 2

        prime_window = repo.primes(start_i, 7)
        gap_window = repo.gaps(start_i, 6)

        require_equal(
            len(prime_window),
            7,
            "Cross-partition prime window length mismatch",
        )
        require_equal(
            len(gap_window),
            6,
            "Cross-partition gap window length mismatch",
        )

        require_array_equal(
            gap_window,
            np.diff(prime_window),
            "Cross-partition gap arithmetic mismatch",
        )


def test_final_left_owned_gap() -> None:
    """
    Validate the final stored left-owned gap coordinate.
    """

    with PrimeQueryRepository() as repo:
        final_i = repo.total_primes

        final_prime = repo.prime(final_i)
        final_gap = repo.gap(final_i)
        final_gap_window = repo.gaps(final_i, 1)

        require(
            final_prime > 0,
            "Final prime is not positive.",
        )
        require(
            final_gap > 0,
            "Final left-owned gap is not positive.",
        )
        require_equal(
            len(final_gap_window),
            1,
            "Final one-gap window length mismatch",
        )
        require_equal(
            int(final_gap_window[0]),
            final_gap,
            "Final scalar and window gap values differ",
        )


def test_numeric_queries() -> None:
    """
    Validate floor, ceiling, and membership semantics.
    """

    with PrimeQueryRepository() as repo:
        n = 1_000_000_000_001

        floor_value = repo.floor_prime(n)
        ceiling_value = repo.ceiling_prime(n)

        require_equal(
            floor_value,
            999_999_999_989,
            "Known floor-prime query mismatch",
        )
        require_equal(
            ceiling_value,
            1_000_000_000_039,
            "Known ceiling-prime query mismatch",
        )
        require_equal(
            repo.contains_prime(n),
            False,
            "Known composite membership query mismatch",
        )

        require_equal(
            repo.floor_prime(0),
            None,
            "Floor below repository extent must be None",
        )
        require_equal(
            repo.ceiling_prime(0),
            2,
            "Ceiling below repository extent mismatch",
        )

        above_extent = repo.range_end + 1

        require_equal(
            repo.floor_prime(above_extent),
            repo.prime(repo.total_primes),
            "Floor above repository extent mismatch",
        )
        require_equal(
            repo.ceiling_prime(above_extent),
            None,
            "Ceiling above repository extent must be None",
        )

        require(
            repo.contains_prime(2),
            "Repository must contain prime 2.",
        )
        require(
            not repo.contains_prime(1),
            "Repository must not contain integer 1.",
        )


def test_zero_length_windows() -> None:
    """
    Validate zero-length prime and gap windows.
    """

    with PrimeQueryRepository() as repo:
        prime_window = repo.primes(1, 0)
        gap_window = repo.gaps(1, 0)

        require_equal(
            len(prime_window),
            0,
            "Zero-length prime window is not empty",
        )
        require_equal(
            len(gap_window),
            0,
            "Zero-length gap window is not empty",
        )
        require_equal(
            str(prime_window.dtype),
            "uint64",
            "Zero-length prime window dtype mismatch",
        )
        require_equal(
            str(gap_window.dtype),
            "uint16",
            "Zero-length gap window dtype mismatch",
        )


def test_invalid_cache_size() -> None:
    """
    Validate cache-size argument enforcement.
    """

    require_raises(
        ValueError,
        lambda: PrimeQueryRepository(cache_size=0),
        "cache_size=0 must be rejected",
    )

    require_raises(
        ValueError,
        lambda: PrimeQueryRepository(cache_size=-1),
        "Negative cache_size must be rejected",
    )


def test_invalid_scalar_coordinates() -> None:
    """
    Validate scalar coordinate bounds.
    """

    with PrimeQueryRepository() as repo:
        require_raises(
            ValueError,
            lambda: repo.prime(0),
            "Prime coordinate zero must be rejected",
        )
        require_raises(
            ValueError,
            lambda: repo.prime(repo.total_primes + 1),
            "Prime coordinate above extent must be rejected",
        )
        require_raises(
            ValueError,
            lambda: repo.gap(0),
            "Gap coordinate zero must be rejected",
        )
        require_raises(
            ValueError,
            lambda: repo.gap(repo.total_gaps + 1),
            "Gap coordinate above extent must be rejected",
        )


def test_invalid_windows() -> None:
    """
    Validate prime and gap window bounds.
    """

    with PrimeQueryRepository() as repo:
        require_raises(
            ValueError,
            lambda: repo.primes(0, 1),
            "Prime window start zero must be rejected",
        )
        require_raises(
            ValueError,
            lambda: repo.gaps(0, 1),
            "Gap window start zero must be rejected",
        )
        require_raises(
            ValueError,
            lambda: repo.primes(1, -1),
            "Negative prime window length must be rejected",
        )
        require_raises(
            ValueError,
            lambda: repo.gaps(1, -1),
            "Negative gap window length must be rejected",
        )
        require_raises(
            ValueError,
            lambda: repo.primes(repo.total_primes, 2),
            "Prime window above extent must be rejected",
        )
        require_raises(
            ValueError,
            lambda: repo.gaps(repo.total_gaps, 2),
            "Gap window above extent must be rejected",
        )


def test_partition_lookup() -> None:
    """
    Validate global prime-index to partition-coordinate mapping.
    """

    with PrimeQueryRepository() as repo:
        first_partition, first_local = (
            repo.partition_for_index(1)
        )

        require_equal(
            first_partition,
            0,
            "First prime partition index mismatch",
        )
        require_equal(
            first_local,
            0,
            "First prime local index mismatch",
        )

        boundary_i = int(
            repo.partitions[0]["last_prime_index"]
        )

        boundary_partition, boundary_local = (
            repo.partition_for_index(boundary_i)
        )

        next_partition, next_local = (
            repo.partition_for_index(boundary_i + 1)
        )

        require_equal(
            boundary_partition,
            0,
            "Boundary prime mapped to wrong partition",
        )
        require_equal(
            boundary_local,
            int(repo.partitions[0]["prime_count"]) - 1,
            "Boundary prime local coordinate mismatch",
        )
        require_equal(
            next_partition,
            1,
            "First prime after boundary mapped incorrectly",
        )
        require_equal(
            next_local,
            0,
            "First local coordinate after boundary mismatch",
        )


def test_query_partition_copy() -> None:
    """
    Validate public partition metadata isolation.
    """

    with PrimeQueryRepository() as repo:
        public_partitions = repo.query_partitions()

        require_equal(
            len(public_partitions),
            len(repo.partitions),
            "Public partition metadata count mismatch",
        )

        require(
            public_partitions is not repo.partitions,
            "query_partitions() returned the internal list object.",
        )


def test_context_manager() -> None:
    """
    Validate context-manager entry and cleanup behavior.
    """

    repo = PrimeQueryRepository(cache_size=2)

    with repo as entered:
        require(
            entered is repo,
            "Context manager returned a different repository object.",
        )

        repo.prime(1)
        repo.gap(1)

    repo.close()

    require(
        True,
        "Context manager cleanup failed.",
    )


def show_window(
    repo: PrimeQueryRepository,
    i: int,
    length: int,
) -> None:
    """
    Display one representative read-only query benchmark.
    """

    print(SUBSEPARATOR)
    print(f"Window: i={i:,}, length={length:,}")

    started = time.perf_counter()
    prime_window = repo.primes(i, length)
    prime_finished = time.perf_counter()

    gap_window = repo.gaps(i, length)
    gap_finished = time.perf_counter()

    print(
        "Prime window runtime : "
        f"{prime_finished - started:.6f} sec"
    )
    print(
        "Gap window runtime   : "
        f"{gap_finished - prime_finished:.6f} sec"
    )

    if length == 0:
        print("Empty window")
        return

    print(
        f"First prime          : "
        f"{int(prime_window[0]):,}"
    )
    print(
        f"Last prime           : "
        f"{int(prime_window[-1]):,}"
    )
    print(
        f"First gap            : "
        f"{int(gap_window[0])}"
    )
    print(
        f"Max gap in window    : "
        f"{int(gap_window.max())}"
    )
    print(
        f"Mean gap in window   : "
        f"{float(gap_window.mean()):.6f}"
    )


def run_contract_tests() -> list[TestResult]:
    """
    Execute the complete deterministic contract suite.
    """

    tests: list[
        tuple[str, Callable[[], None]]
    ] = [
        (
            "initialization_and_summary",
            test_initialization_and_summary,
        ),
        (
            "compatibility_alias",
            test_compatibility_alias,
        ),
        (
            "basic_scalar_coordinates",
            test_basic_scalar_coordinates,
        ),
        (
            "first_partition_boundary",
            test_first_partition_boundary,
        ),
        (
            "cross_partition_windows",
            test_cross_partition_windows,
        ),
        (
            "final_left_owned_gap",
            test_final_left_owned_gap,
        ),
        (
            "numeric_queries",
            test_numeric_queries,
        ),
        (
            "zero_length_windows",
            test_zero_length_windows,
        ),
        (
            "invalid_cache_size",
            test_invalid_cache_size,
        ),
        (
            "invalid_scalar_coordinates",
            test_invalid_scalar_coordinates,
        ),
        (
            "invalid_windows",
            test_invalid_windows,
        ),
        (
            "partition_lookup",
            test_partition_lookup,
        ),
        (
            "query_partition_copy",
            test_query_partition_copy,
        ),
        (
            "context_manager",
            test_context_manager,
        ),
    ]

    results: list[TestResult] = []

    for name, function in tests:
        result = run_test(name, function)
        results.append(result)

        status = "PASSED" if result.passed else "FAILED"

        print(
            f"[{status}] "
            f"{result.name} "
            f"({result.runtime_sec:.6f} sec)"
        )

        if result.message:
            print(f"         {result.message}")

    return results


def main() -> int:
    """
    Run the PrimeNet query repository contract suite.
    """

    print(SEPARATOR)
    print(
        f"PrimeNet Query Repository Contract Test "
        f"v{TEST_VERSION}"
    )
    print(SEPARATOR)

    suite_started = time.perf_counter()

    print()
    print("Repository contract tests")
    print(SUBSEPARATOR)

    results = run_contract_tests()

    passed = sum(
        1
        for result in results
        if result.passed
    )
    failed = len(results) - passed

    print()
    print("Representative query windows")

    try:
        with PrimeQueryRepository() as repo:
            print(SUBSEPARATOR)
            print(repo.summary())

            show_window(repo, 1, 20)
            show_window(repo, 1_000_000, 1_000)
            show_window(repo, 100_000_000, 10_000)

    except Exception as exc:
        failed += 1

        print(SUBSEPARATOR)
        print(
            "[FAILED] Representative query windows: "
            f"{type(exc).__name__}: {exc}"
        )

    total_runtime = time.perf_counter() - suite_started

    print()
    print(SEPARATOR)
    print("Query repository contract test complete")
    print(SEPARATOR)
    print(f"Tests executed : {len(results)}")
    print(f"Passed         : {passed}")
    print(f"Failed         : {failed}")
    print(f"Runtime        : {total_runtime:.6f} sec")
    print(SEPARATOR)

    if failed:
        print()
        print("[FAILED]")
        print(
            "PrimeNet index-coordinate query contract "
            "validation failed."
        )
        print(SEPARATOR)
        return 1

    print()
    print("[ACCEPTED]")
    print(
        "PrimeNet index-coordinate query API satisfies "
        "the tested read-only contract."
    )
    print(SEPARATOR)

    return 0


if __name__ == "__main__":
    sys.exit(main())