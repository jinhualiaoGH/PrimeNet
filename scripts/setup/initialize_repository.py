from pathlib import Path
from datetime import datetime
import json
import platform


ROOT = Path("C:/PrimeNet")
REPOSITORY = ROOT / "repository"
METADATA = REPOSITORY / "metadata"
LOGS = ROOT / "logs"


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_repository_folders() -> None:
    folders = [
        REPOSITORY,
        REPOSITORY / "raw",
        REPOSITORY / "raw" / "primes",
        REPOSITORY / "raw" / "gaps",
        REPOSITORY / "raw" / "events",
        REPOSITORY / "processed",
        REPOSITORY / "indexes",
        METADATA,
        LOGS,
    ]

    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)


def create_repository_info() -> None:
    path = METADATA / "repository_info.json"

    if path.exists():
        data = read_json(path)
        data["last_checked_at"] = now()
        data["status"] = "active"
    else:
        data = {
            "repository_name": "Prime Repository",
            "project": "PrimeNet",
            "version": "1.0.0",
            "created_at": now(),
            "last_checked_at": now(),
            "root": str(REPOSITORY),
            "description": (
                "Prime Repository stores raw and processed arithmetic observation data "
                "for the PrimeNet Observatory."
            ),
            "status": "active",
            "largest_integer": None,
            "prime_count": None,
            "gap_event_count": None,
            "raw_data_paths": {
                "primes": "repository/raw/primes",
                "gaps": "repository/raw/gaps",
                "events": "repository/raw/events",
            },
            "processed_data_path": "repository/processed",
            "index_path": "repository/indexes",
            "metadata_path": "repository/metadata",
        }

    write_json(path, data)
    print(f"  created/updated: {path}")


def create_datasets_index() -> None:
    path = METADATA / "datasets.json"

    if path.exists():
        data = read_json(path)
        data["last_updated_at"] = now()
    else:
        data = {
            "project": "PrimeNet",
            "file": "datasets.json",
            "created_at": now(),
            "last_updated_at": now(),
            "description": "Registry of datasets known to the Prime Repository.",
            "datasets": [],
        }

    write_json(path, data)
    print(f"  created/updated: {path}")


def create_statistics_file() -> None:
    path = METADATA / "statistics.json"

    if path.exists():
        data = read_json(path)
        data["last_updated_at"] = now()
    else:
        data = {
            "project": "PrimeNet",
            "file": "statistics.json",
            "created_at": now(),
            "last_updated_at": now(),
            "description": "High-level statistics for the Prime Repository.",
            "statistics": {
                "largest_integer": None,
                "prime_count": None,
                "gap_event_count": None,
                "number_of_prime_files": 0,
                "number_of_gap_files": 0,
                "number_of_event_files": 0,
                "repository_size_bytes": 0,
            },
        }

    write_json(path, data)
    print(f"  created/updated: {path}")


def create_repository_history() -> None:
    path = METADATA / "repository_history.json"

    event = {
        "timestamp": now(),
        "event": "initialize_repository",
        "description": "Prime Repository initialized or verified.",
        "status": "completed",
    }

    if path.exists():
        data = read_json(path)
        data.setdefault("history", []).append(event)
        data["last_updated_at"] = now()
    else:
        data = {
            "project": "PrimeNet",
            "file": "repository_history.json",
            "created_at": now(),
            "last_updated_at": now(),
            "description": "Chronological history of repository initialization and updates.",
            "history": [event],
        }

    write_json(path, data)
    print(f"  created/updated: {path}")


def create_checksum_manifest() -> None:
    path = METADATA / "checksum_manifest.json"

    if path.exists():
        data = read_json(path)
        data["last_updated_at"] = now()
    else:
        data = {
            "project": "PrimeNet",
            "file": "checksum_manifest.json",
            "created_at": now(),
            "last_updated_at": now(),
            "description": (
                "Manifest for file checksums. Future repository audit tools will "
                "populate this file."
            ),
            "algorithm": "sha256",
            "files": [],
        }

    write_json(path, data)
    print(f"  created/updated: {path}")


def create_repository_readme() -> None:
    path = REPOSITORY / "README.md"

    if path.exists():
        print(f"  exists, skipped: {path}")
        return

    text = """# Prime Repository

The Prime Repository is the data foundation of PrimeNet.

It stores raw and processed arithmetic observation data, including:

- prime number ranges
- prime gap sequences
- fixed-gap event languages
- transition datasets
- processed observatory products
- metadata and indexes

The repository is designed to support reproducible, large-scale observational
studies of prime information structures.

Recommended organization:

repository/
    raw/
        primes/
        gaps/
        events/
    processed/
    indexes/
    metadata/

Raw data should be treated as immutable whenever possible.
Processed data and indexes may be regenerated by observatory instruments.
"""

    path.write_text(text, encoding="utf-8")
    print(f"  created: {path}")