from pathlib import Path
from datetime import datetime
import csv
import hashlib
import json
import platform
import os


ROOT = Path("C:/PrimeNet")
REPOSITORY = ROOT / "repository"
CATALOG = ROOT / "catalog"
LOGS = ROOT / "logs"

INVENTORY_CSV = CATALOG / "repository_inventory.csv"
INVENTORY_JSON = CATALOG / "repository_inventory.json"
SUMMARY_JSON = CATALOG / "repository_summary.json"

COMPUTE_SHA256 = False


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def safe_relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)

    return h.hexdigest()


def classify_file(path: Path) -> str:
    p = str(path).lower().replace("\\", "/")
    name = path.name.lower()
    suffix = path.suffix.lower()

    if "/repository/raw/primes/" in p:
        return "raw_prime_file"

    if "/repository/raw/gaps/" in p:
        return "raw_gap_file"

    if "/repository/raw/events/" in p:
        return "raw_event_file"

    if "/repository/processed/" in p:
        return "processed_repository_file"

    if "/repository/indexes/" in p:
        return "repository_index_file"

    if "/repository/metadata/" in p:
        if "checksum" in name or "checksums" in name:
            return "checksum_metadata_file"
        if "audit" in name:
            return "audit_metadata_file"
        if "index" in name:
            return "index_metadata_file"
        if "generation" in name or "log" in name:
            return "generation_log_file"
        return "repository_metadata_file"

    if suffix in [".npy", ".npz"]:
        if "prime" in name:
            return "prime_array_file"
        if "gap" in name:
            return "gap_array_file"
        if "event" in name:
            return "event_array_file"
        return "numeric_array_file"

    if suffix in [".csv", ".tsv"]:
        return "tabular_file"

    if suffix in [".json", ".jsonl"]:
        return "json_metadata_file"

    if suffix in [".txt", ".md", ".log"]:
        return "text_document"

    if suffix in [".png", ".jpg", ".jpeg", ".svg", ".pdf"]:
        return "figure_or_document"

    return "unclassified_file"


def infer_dataset_role(path: Path) -> str:
    p = str(path).lower().replace("\\", "/")
    name = path.name.lower()

    if "prime" in name or "/raw/primes/" in p:
        return "prime_numbers"

    if "gap" in name or "/raw/gaps/" in p:
        return "prime_gaps"

    if "event" in name or "/raw/events/" in p:
        return "event_language"

    if "transition" in name:
        return "transition_data"

    if "entropy" in name:
        return "entropy_data"

    if "invariant" in name:
        return "invariant_data"

    if "taxonomy" in name:
        return "taxonomy_data"

    if "runtime" in name:
        return "runtime_data"

    if "audit" in name:
        return "audit_metadata"

    if "checksum" in name:
        return "checksum_metadata"

    if "index" in name:
        return "index_metadata"

    return "general_repository_asset"


def discover_files() -> list[dict]:
    records = []

    if not REPOSITORY.exists():
        print(f"Repository folder not found: {REPOSITORY}")
        return records

    print("\nScanning repository files...\n")

    for path in REPOSITORY.rglob("*"):
        if not path.is_file():
            continue

        try:
            stat = path.stat()
        except OSError:
            continue

        relative_path = safe_relative_path(path, ROOT)

        record = {
            "asset_id": "",
            "file_name": path.name,
            "relative_path": relative_path,
            "absolute_path": str(path),
            "extension": path.suffix.lower(),
            "category": classify_file(path),
            "dataset_role": infer_dataset_role(path),
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 6),
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(timespec="seconds"),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            "sha256": "",
            "status": "discovered",
        }

        if COMPUTE_SHA256:
            try:
                record["sha256"] = sha256_file(path)
            except Exception as exc:
                record["sha256"] = f"ERROR: {exc}"

        records.append(record)

    records.sort(key=lambda r: r["relative_path"])

    for i, record in enumerate(records, start=1):
        record["asset_id"] = f"REPO_ASSET_{i:06d}"

    return records


def summarize_records(records: list[dict]) -> dict:
    total_size = sum(r["size_bytes"] for r in records)

    by_category = {}
    by_role = {}
    by_extension = {}

    for r in records:
        by_category[r["category"]] = by_category.get(r["category"], 0) + 1
        by_role[r["dataset_role"]] = by_role.get(r["dataset_role"], 0) + 1
        by_extension[r["extension"]] = by_extension.get(r["extension"], 0) + 1

    summary = {
        "project": "PrimeNet",
        "script": "02_discover_repository.py",
        "created_at": now(),
        "repository_path": str(REPOSITORY),
        "total_files": len(records),
        "total_size_bytes": total_size,
        "total_size_gb": round(total_size / (1024 ** 3), 6),
        "by_category": dict(sorted(by_category.items())),
        "by_dataset_role": dict(sorted(by_role.items())),
        "by_extension": dict(sorted(by_extension.items())),
        "sha256_computed": COMPUTE_SHA256,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
    }

    return summary


def write_inventory_csv(records: list[dict]) -> None:
    CATALOG.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "asset_id",
        "file_name",
        "relative_path",
        "absolute_path",
        "extension",
        "category",
        "dataset_role",
        "size_bytes",
        "size_mb",
        "created_at",
        "modified_at",
        "sha256",
        "status",
    ]

    with INVENTORY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"  wrote: {INVENTORY_CSV}")


def write_inventory_json(records: list[dict]) -> None:
    data = {
        "project": "PrimeNet",
        "file": "repository_inventory.json",
        "created_at": now(),
        "description": "Discovered file inventory for the Prime Repository.",
        "records": records,
    }

    INVENTORY_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"  wrote: {INVENTORY_JSON}")


def write_summary_json(summary: dict) -> None:
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"  wrote: {SUMMARY_JSON}")


def print_summary(summary: dict) -> None:
    print("\nRepository Discovery Summary")
    print("-" * 80)
    print(f"Repository:      {summary['repository_path']}")
    print(f"Total files:     {summary['total_files']}")
    print(f"Total size:      {summary['total_size_gb']} GB")
    print(f"SHA256 enabled:  {summary['sha256_computed']}")

    print("\nBy category:")
    for key, value in summary["by_category"].items():
        print(f"  {key:30s} {value}")

    print("\nBy dataset role:")
    for key, value in summary["by_dataset_role"].items():
        print(f"  {key:30s} {value}")


def write_log(summary: dict) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)

    path = LOGS / "02_discover_repository.log"

    with path.open("a", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write(f"[{now()}] 02_discover_repository.py completed\n")
        f.write(f"repository={summary['repository_path']}\n")
        f.write(f"total_files={summary['total_files']}\n")
        f.write(f"total_size_gb={summary['total_size_gb']}\n")
        f.write(f"sha256_computed={summary['sha256_computed']}\n")

    print(f"\n  updated log: {path}")


def update_manifest(summary: dict) -> None:
    manifest_path = ROOT / "manifest.json"

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {
            "project": "PrimeNet",
            "version": "1.0.0",
            "created_at": now(),
        }

    manifest["last_updated_at"] = now()

    manifest["repository_discovery"] = {
        "last_discovered_at": summary["created_at"],
        "inventory_csv": "catalog/repository_inventory.csv",
        "inventory_json": "catalog/repository_inventory.json",
        "summary_json": "catalog/repository_summary.json",
        "total_files": summary["total_files"],
        "total_size_gb": summary["total_size_gb"],
        "sha256_computed": summary["sha256_computed"],
    }

    setup_history = manifest.setdefault("setup_history", [])
    setup_history.append(
        {
            "timestamp": now(),
            "script": "02_discover_repository.py",
            "action": "discover_repository",
            "status": "completed",
            "total_files": summary["total_files"],
            "total_size_gb": summary["total_size_gb"],
        }
    )

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  updated manifest: {manifest_path}")


def main() -> None:
    print("=" * 80)
    print("PrimeNet Repository Discovery v1.0")
    print("=" * 80)

    records = discover_files()
    summary = summarize_records(records)

    print("\nWriting discovery products...\n")

    write_inventory_csv(records)
    write_inventory_json(records)
    write_summary_json(summary)
    update_manifest(summary)
    write_log(summary)
    print_summary(summary)

    print("\n" + "=" * 80)
    print("Repository discovery completed.")
    print("=" * 80)


if __name__ == "__main__":
    main()