from pathlib import Path
from datetime import datetime
import json
import platform


ROOT = Path("C:/PrimeNet")


DIRECTORIES = [
    "repository",
    "repository/raw",
    "repository/raw/primes",
    "repository/raw/gaps",
    "repository/raw/events",
    "repository/processed",
    "repository/indexes",
    "repository/metadata",

    "observatories",
    "observatories/entropy",
    "observatories/transition",
    "observatories/invariant",
    "observatories/runtime",
    "observatories/taxonomy",
    "observatories/geometry",
    "observatories/spectrum",
    "observatories/validation",
    "observatories/compression",
    "observatories/flow",

    "atlases",
    "atlases/entropy",
    "atlases/transition",
    "atlases/invariant",
    "atlases/runtime",
    "atlases/taxonomy",
    "atlases/geometry",
    "atlases/spectrum",
    "atlases/flow",

    "catalog",
    "config",
    "docs",
    "figures",
    "papers",
    "results",
    "scripts",
    "scripts/setup",
    "tests",
    "logs",
    "tmp",
]


CATALOG_FILES = {
    "catalog/observations.csv": (
        "observation_id,date,dataset,instrument,parameters,runtime_sec,"
        "output_path,status,notes\n"
    ),
    "catalog/instruments.csv": (
        "instrument_id,name,version,description,script_path,status\n"
    ),
    "catalog/datasets.csv": (
        "dataset_id,name,path,type,created_at,description,status\n"
    ),
}


TEXT_FILES = {
    "README.md": """# PrimeNet

PrimeNet: An Observatory for Prime Information Structures.

PrimeNet is an open, reproducible, data-driven framework for observing,
measuring, cataloging, and studying information structures arising from
prime distributions.

Motto:

Observe. Measure. Validate. Explore.
""",

    "VERSION": "1.0.0\n",

    "CHANGELOG.md": """# Changelog

## v1.0.0

- Initial PrimeNet observatory architecture.
- Repository, observatories, atlases, catalog, and documentation structure.
""",

    "docs/architecture.md": """# PrimeNet Observatory Architecture

PrimeNet is organized as a scientific observatory.

Core layers:

1. Prime Repository
2. Observatory Instruments
3. Information Products
4. Atlases
5. Catalog
6. Research Layer

Observation first. Interpretation second.
""",

    "docs/observatory_design.md": """# Observatory Design

Each observatory is treated as a scientific instrument.

Every instrument should:

- read standardized repository data
- perform one class of measurement
- generate reproducible outputs
- write catalog metadata
- preserve runtime and validation information
""",

    "config/config.yaml": """primenet:
  version: "1.0.0"
  root: "C:/PrimeNet"

repository:
  raw: "repository/raw"
  processed: "repository/processed"
  metadata: "repository/metadata"

catalog:
  observations: "catalog/observations.csv"
  instruments: "catalog/instruments.csv"
  datasets: "catalog/datasets.csv"
""",
}


INSTRUMENTS = [
    ("OBS001", "Entropy Observatory", "1.0", "Measures entropy of prime event languages", "observatories/entropy"),
    ("OBS002", "Transition Observatory", "1.0", "Measures transition structure between arithmetic states", "observatories/transition"),
    ("OBS003", "Invariant Observatory", "1.0", "Searches for stable information invariants", "observatories/invariant"),
    ("OBS004", "Runtime Observatory", "1.0", "Tracks runtime and computational scaling", "observatories/runtime"),
    ("OBS005", "Taxonomy Observatory", "1.0", "Classifies gap and event information families", "observatories/taxonomy"),
    ("OBS006", "Geometry Observatory", "1.0", "Studies information geometry of prime structures", "observatories/geometry"),
    ("OBS007", "Spectrum Observatory", "1.0", "Analyzes gap/event spectra across arithmetic states", "observatories/spectrum"),
    ("OBS008", "Validation Observatory", "1.0", "Runs validation and counterexample searches", "observatories/validation"),
    ("OBS009", "Compression Observatory", "1.0", "Measures compressibility and predictive structure", "observatories/compression"),
    ("OBS010", "Flow Observatory", "1.0", "Studies directed flow among gap states", "observatories/flow"),
]


def create_directories(root: Path) -> None:
    print("\n[1/5] Creating PrimeNet directory structure...\n")

    for directory in DIRECTORIES:
        path = root / directory
        path.mkdir(parents=True, exist_ok=True)
        print(f"  created/verified: {path}")


def create_text_files(root: Path) -> None:
    print("\n[2/5] Creating documentation and config files...\n")

    for relative_path, content in TEXT_FILES.items():
        path = root / relative_path
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            print(f"  created: {path}")
        else:
            print(f"  exists, skipped: {path}")


def create_catalog_files(root: Path) -> None:
    print("\n[3/5] Creating catalog files...\n")

    for relative_path, header in CATALOG_FILES.items():
        path = root / relative_path
        if not path.exists():
            path.write_text(header, encoding="utf-8")
            print(f"  created: {path}")
        else:
            print(f"  exists, skipped: {path}")


def register_instruments(root: Path) -> None:
    print("\n[4/5] Registering observatory instruments...\n")

    path = root / "catalog" / "instruments.csv"

    lines = [
        "instrument_id,name,version,description,script_path,status\n"
    ]

    for instrument_id, name, version, description, script_path in INSTRUMENTS:
        line = (
            f"{instrument_id},"
            f"{name},"
            f"{version},"
            f"{description},"
            f"{script_path},"
            f"active\n"
        )
        lines.append(line)

    path.write_text("".join(lines), encoding="utf-8")
    print(f"  updated: {path}")


def create_manifest(root: Path) -> None:
    print("\n[5/5] Creating PrimeNet manifest...\n")

    manifest = {
        "project": "PrimeNet",
        "title": "PrimeNet: An Observatory for Prime Information Structures",
        "version": "1.0.0",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "architecture": {
            "repository": "Prime Repository",
            "observatories": "Scientific instruments",
            "atlases": "Aggregated information products",
            "catalog": "Observation and instrument registry",
            "papers": "Research outputs",
        },
        "motto": "Observe. Measure. Validate. Explore.",
    }

    path = root / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  created/updated: {path}")


def validate_installation(root: Path) -> None:
    print("\nValidating PrimeNet installation...\n")

    missing = []

    for directory in DIRECTORIES:
        path = root / directory
        if not path.exists():
            missing.append(str(path))

    required_files = [
        "README.md",
        "VERSION",
        "CHANGELOG.md",
        "manifest.json",
        "config/config.yaml",
        "catalog/observations.csv",
        "catalog/instruments.csv",
        "catalog/datasets.csv",
        "docs/architecture.md",
        "docs/observatory_design.md",
    ]

    for relative_path in required_files:
        path = root / relative_path
        if not path.exists():
            missing.append(str(path))

    if missing:
        print("PrimeNet structure validation FAILED.")
        print("\nMissing items:")
        for item in missing:
            print(f"  {item}")
    else:
        print("PrimeNet structure validation PASSED.")


def main() -> None:
    print("=" * 80)
    print("PrimeNet Structure Creator v1.0")
    print("=" * 80)
    print(f"Root directory: {ROOT}")

    create_directories(ROOT)
    create_text_files(ROOT)
    create_catalog_files(ROOT)
    register_instruments(ROOT)
    create_manifest(ROOT)
    validate_installation(ROOT)

    print("\n" + "=" * 80)
    print("PrimeNet v1.0 folder structure is ready.")
    print("=" * 80)


if __name__ == "__main__":
    main()