from pathlib import Path
from datetime import datetime
import csv
import json
import platform


ROOT = Path("C:/PrimeNet")
CATALOG = ROOT / "catalog"
LOGS = ROOT / "logs"

INVENTORY_CSV = CATALOG / "repository_inventory.csv"
ASSET_REGISTRY_CSV = CATALOG / "asset_registry.csv"
ASSET_REGISTRY_JSON = CATALOG / "asset_registry.json"
ASSET_SUMMARY_JSON = CATALOG / "asset_summary.json"


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_inventory() -> list[dict]:
    if not INVENTORY_CSV.exists():
        raise FileNotFoundError(
            f"Missing inventory file: {INVENTORY_CSV}\n"
            "Please run 02_discover_repository.py first."
        )

    with INVENTORY_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def determine_asset_type(record: dict) -> str:
    category = record.get("category", "")
    role = record.get("dataset_role", "")
    name = record.get("file_name", "").lower()
    path = record.get("relative_path", "").lower()

    if "prime" in role or "prime" in name:
        return "dataset_prime_numbers"

    if "gap" in role or "gap" in name:
        return "dataset_prime_gaps"

    if "event" in role or "event" in name:
        return "dataset_event_language"

    if "transition" in role or "transition" in name:
        return "dataset_transition"

    if "entropy" in role or "entropy" in name:
        return "dataset_entropy"

    if "invariant" in role or "invariant" in name:
        return "dataset_invariant"

    if "taxonomy" in role or "taxonomy" in name:
        return "dataset_taxonomy"

    if "runtime" in role or "runtime" in name:
        return "dataset_runtime"

    if "checksum" in category or "checksum" in role or "checksum" in name:
        return "metadata_checksum"

    if "audit" in category or "audit" in role or "audit" in name:
        return "metadata_audit"

    if "index" in category or "index" in role or "index" in name:
        return "metadata_index"

    if "generation" in category or "generation" in name or "log" in name:
        return "metadata_generation_log"

    if "/figures/" in path or name.endswith((".png", ".jpg", ".jpeg", ".svg")):
        return "figure"

    if "/papers/" in path or name.endswith((".pdf", ".docx", ".tex")):
        return "publication_or_manuscript"

    if name.endswith((".md", ".txt")):
        return "documentation"

    if name.endswith((".json", ".csv")):
        return "structured_metadata"

    return "general_asset"


def make_asset_id(index: int, asset_type: str) -> str:
    if asset_type.startswith("dataset"):
        prefix = "DATA"
    elif asset_type.startswith("metadata"):
        prefix = "META"
    elif asset_type == "figure":
        prefix = "FIG"
    elif asset_type == "publication_or_manuscript":
        prefix = "PUB"
    elif asset_type == "documentation":
        prefix = "DOC"
    else:
        prefix = "ASSET"

    return f"{prefix}{index:06d}"


def build_asset_records(inventory: list[dict]) -> list[dict]:
    records = []

    for i, item in enumerate(inventory, start=1):
        asset_type = determine_asset_type(item)

        record = {
            "asset_id": make_asset_id(i, asset_type),
            "source_asset_id": item.get("asset_id", ""),
            "asset_type": asset_type,
            "asset_name": item.get("file_name", ""),
            "relative_path": item.get("relative_path", ""),
            "category": item.get("category", ""),
            "dataset_role": item.get("dataset_role", ""),
            "extension": item.get("extension", ""),
            "size_bytes": item.get("size_bytes", ""),
            "size_mb": item.get("size_mb", ""),
            "created_at": item.get("created_at", ""),
            "modified_at": item.get("modified_at", ""),
            "registered_at": now(),
            "status": "registered",
            "provenance": "discovered_by_02_discover_repository.py",
            "notes": "",
        }

        records.append(record)

    return records


def summarize_assets(records: list[dict]) -> dict:
    by_asset_type = {}
    total_size_bytes = 0

    for r in records:
        asset_type = r["asset_type"]
        by_asset_type[asset_type] = by_asset_type.get(asset_type, 0) + 1

        try:
            total_size_bytes += int(float(r.get("size_bytes", 0)))
        except ValueError:
            pass

    summary = {
        "project": "PrimeNet",
        "script": "03_register_assets.py",
        "created_at": now(),
        "total_assets": len(records),
        "total_size_bytes": total_size_bytes,
        "total_size_gb": round(total_size_bytes / (1024 ** 3), 6),
        "by_asset_type": dict(sorted(by_asset_type.items())),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
    }

    return summary


def write_asset_registry_csv(records: list[dict]) -> None:
    CATALOG.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "asset_id",
        "source_asset_id",
        "asset_type",
        "asset_name",
        "relative_path",
        "category",
        "dataset_role",
        "extension",
        "size_bytes",
        "size_mb",
        "created_at",
        "modified_at",
        "registered_at",
        "status",
        "provenance",
        "notes",
    ]

    with ASSET_REGISTRY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"  wrote: {ASSET_REGISTRY_CSV}")


def write_asset_registry_json(records: list[dict]) -> None:
    data = {
        "project": "PrimeNet",
        "file": "asset_registry.json",
        "created_at": now(),
        "description": "PrimeNet registered asset registry generated from repository discovery.",
        "records": records,
    }

    ASSET_REGISTRY_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"  wrote: {ASSET_REGISTRY_JSON}")


def write_asset_summary(summary: dict) -> None:
    ASSET_SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"  wrote: {ASSET_SUMMARY_JSON}")


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

    manifest["asset_registry"] = {
        "last_registered_at": summary["created_at"],
        "asset_registry_csv": "catalog/asset_registry.csv",
        "asset_registry_json": "catalog/asset_registry.json",
        "asset_summary_json": "catalog/asset_summary.json",
        "total_assets": summary["total_assets"],
        "total_size_gb": summary["total_size_gb"],
    }

    setup_history = manifest.setdefault("setup_history", [])
    setup_history.append(
        {
            "timestamp": now(),
            "script": "03_register_assets.py",
            "action": "register_assets",
            "status": "completed",
            "total_assets": summary["total_assets"],
            "total_size_gb": summary["total_size_gb"],
        }
    )

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  updated manifest: {manifest_path}")


def write_log(summary: dict) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)

    path = LOGS / "03_register_assets.log"

    with path.open("a", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write(f"[{now()}] 03_register_assets.py completed\n")
        f.write(f"total_assets={summary['total_assets']}\n")
        f.write(f"total_size_gb={summary['total_size_gb']}\n")

    print(f"  updated log: {path}")


def print_summary(summary: dict) -> None:
    print("\nAsset Registration Summary")
    print("-" * 80)
    print(f"Total assets: {summary['total_assets']}")
    print(f"Total size:   {summary['total_size_gb']} GB")

    print("\nBy asset type:")
    for key, value in summary["by_asset_type"].items():
        print(f"  {key:35s} {value}")


def main() -> None:
    print("=" * 80)
    print("PrimeNet Asset Registry v1.0")
    print("=" * 80)

    print("\nReading repository inventory...\n")
    inventory = read_inventory()

    print(f"  inventory records loaded: {len(inventory)}")

    print("\nRegistering assets...\n")
    assets = build_asset_records(inventory)

    print("Writing asset registry products...\n")
    write_asset_registry_csv(assets)
    write_asset_registry_json(assets)

    summary = summarize_assets(assets)
    write_asset_summary(summary)
    update_manifest(summary)
    write_log(summary)
    print_summary(summary)

    print("\n" + "=" * 80)
    print("Asset registration completed.")
    print("=" * 80)


if __name__ == "__main__":
    main()