"""
PrimeNet Bootstrap

Creates the standard Instruments package structure.
"""

from pathlib import Path


PACKAGES = [
    "instruments",
    "instruments/matrix",
    "instruments/transition",
    "instruments/entropy",
    "instruments/geometry",
    "instruments/runtime",
    "instruments/validation",
    "instruments/taxonomy",
    "instruments/spectrum",
    "instruments/repository",
]


INIT_TEXT = '''"""
PrimeNet Instruments Package
"""
'''


def create_package(root: Path, package: str) -> None:
    folder = root / package
    folder.mkdir(parents=True, exist_ok=True)

    init_file = folder / "__init__.py"

    if not init_file.exists():
        init_file.write_text(INIT_TEXT, encoding="utf-8")

    print(f"✓ {folder}")


def main() -> None:

    project_root = Path(__file__).resolve().parents[1]

    print("=" * 70)
    print("PrimeNet Instrument Bootstrap")
    print("=" * 70)

    for package in PACKAGES:
        create_package(project_root, package)

    print()
    print("Instrument package structure created successfully.")
    print("=" * 70)


if __name__ == "__main__":
    main()