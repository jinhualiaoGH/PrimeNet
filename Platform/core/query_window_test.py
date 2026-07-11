"""
PrimeNet Query Window Test v1.0.0

Run:
    cd C:\\PrimeNet\\Platform
    py -m core.query_window_test
"""

from __future__ import annotations

import time

from Platform.core.query_repository import PrimeRepository


def show_window(repo: PrimeRepository, i: int, length: int) -> None:
    print("-" * 80)
    print(f"Window: i={i:,}, length={length:,}")

    t0 = time.time()
    primes = repo.primes(i, length)
    t1 = time.time()

    gaps = repo.gaps(i, length)
    t2 = time.time()

    print(f"Prime window runtime : {t1 - t0:.6f} sec")
    print(f"Gap window runtime   : {t2 - t1:.6f} sec")

    print(f"First prime          : {int(primes[0]):,}")
    print(f"Last prime           : {int(primes[-1]):,}")
    print(f"First gap            : {int(gaps[0])}")
    print(f"Max gap in window    : {int(gaps.max())}")
    print(f"Mean gap in window   : {float(gaps.mean()):.6f}")


def main() -> None:
    print("=" * 80)
    print("PrimeNet Query Window Test v1.0.0")
    print("=" * 80)

    repo = PrimeRepository()
    print(repo.summary())

    show_window(repo, 1, 20)
    show_window(repo, 1_000_000, 1_000)
    show_window(repo, 100_000_000, 10_000)

    print("=" * 80)


if __name__ == "__main__":
    main()
