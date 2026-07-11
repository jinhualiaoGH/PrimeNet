"""
PrimeNet Platform Bootstrap
create_directory_structure.py

Creates the canonical PrimeNet v1.0 directory structure.

This script is safe to run multiple times.
Existing directories are not overwritten or deleted.
"""

from pathlib import Path
from datetime import datetime


PLATFORM_ROOT = Path(r"C:\PrimeNet\Platform")
REPOSITORY_ROOT = Path(r"E:\PrimeNet\Repository")
PRODUCTS_ROOT = Path(r"E:\PrimeNet\Products")


PLATFORM_DIRS = [
    "bootstrap",
    "core",
    "observatories",
    "instruments",
    "registry",
    "metadata",
    "config",
    "docs",
    "docs/architecture",
    "docs/developer",
    "docs/specifications",
    "docs/roadmap",
    "tests",
    "examples",
]

REPOSITORY_DIRS = [
    "ranges",
    "index",
    "manifests",
    "backups",
    "scripts",
]

PRODUCTS_DIRS = [
    "results",
    "figures",
    "atlases",
    "reports",
    "archives",
    "publications",
]


def create_dirs(root: Path, dirs: list[str], label: str) -> tuple[int, int]:
    print()
    print(f"Creating {label}:")
    print("-" * 60)

    created = 0
    existing = 0

    root.mkdir(parents=True, exist_ok=True)

    for d in dirs:
        path = root / d
        if path.exists():
            print(f"[EXISTS ] {path}")
            existing += 1
        else:
            path.mkdir(parents=True, exist_ok=True)
            print(f"[CREATED] {path}")
            created += 1

    return created, existing


def main() -> None:
    print("=" * 70)
    print("PrimeNet Platform v1.0 Bootstrap")
    print("Create Directory Structure")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat(timespec='seconds')}")

    p_created, p_existing = create_dirs(
        PLATFORM_ROOT,
        PLATFORM_DIRS,
        "PrimeNet Platform",
    )

    r_created, r_existing = create_dirs(
        REPOSITORY_ROOT,
        REPOSITORY_DIRS,
        "Prime Repository",
    )

    pr_created, pr_existing = create_dirs(
        PRODUCTS_ROOT,
        PRODUCTS_DIRS,
        "PrimeNet Products",
    )

    print()
    print("=" * 70)
    print("Bootstrap Summary")
    print("=" * 70)
    print(f"Platform root:   {PLATFORM_ROOT}")
    print(f"Repository root: {REPOSITORY_ROOT}")
    print(f"Products root:   {PRODUCTS_ROOT}")
    print()
    print(f"Platform:   {p_created} created, {p_existing} already existed")
    print(f"Repository: {r_created} created, {r_existing} already existed")
    print(f"Products:   {pr_created} created, {pr_existing} already existed")
    print()
    print("PrimeNet directory structure is ready.")
    print("=" * 70)


if __name__ == "__main__":
    main()