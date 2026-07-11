"""
PrimeNet Registry v2

Automatic observatory discovery from:

    observatories/*/metadata.py
    observatories/*/observatory.yaml
"""

from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class ObservatoryRecord:
    folder: str
    path: str
    observatory_id: str
    name: str
    version: str
    category: str
    description: str
    status: str
    observatory_class: str | None
    supported_instruments: list[str]
    products: list[str]
    dependencies: list[str]


class PrimeNetRegistry:
    """
    Discovers and catalogs PrimeNet observatories.

    Registry v2 does not manually register observatories.
    It scans observatories/ and reads metadata.py + observatory.yaml.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else Path.cwd()
        self.observatories_dir = self.root / "observatories"

        self.records: list[ObservatoryRecord] = []
        self.errors: list[str] = []

    def discover(self) -> list[ObservatoryRecord]:
        self.records = []
        self.errors = []

        if not self.observatories_dir.exists():
            self.errors.append(f"Missing observatories directory: {self.observatories_dir}")
            return self.records

        for folder in sorted(self.observatories_dir.iterdir()):
            if not folder.is_dir():
                continue

            if folder.name.startswith("__"):
                continue

            metadata_path = folder / "metadata.py"
            yaml_path = folder / "observatory.yaml"

            if not metadata_path.exists() and not yaml_path.exists():
                continue

            if not metadata_path.exists():
                self.errors.append(f"{folder.name}: missing metadata.py")
                continue

            if not yaml_path.exists():
                self.errors.append(f"{folder.name}: missing observatory.yaml")
                continue

            try:
                metadata = self._load_metadata(metadata_path)
                yaml_data = self._load_simple_yaml(yaml_path)

                record = ObservatoryRecord(
                    folder=folder.name,
                    path=str(folder),
                    observatory_id=str(metadata.get("OBSERVATORY_ID", yaml_data.get("id", ""))),
                    name=str(metadata.get("NAME", yaml_data.get("name", folder.name))),
                    version=str(metadata.get("VERSION", yaml_data.get("version", ""))),
                    category=str(metadata.get("CATEGORY", yaml_data.get("category", ""))),
                    description=str(metadata.get("DESCRIPTION", yaml_data.get("description", ""))),
                    status=str(yaml_data.get("status", "")),
                    observatory_class=yaml_data.get("observatory"),
                    supported_instruments=list(metadata.get("SUPPORTED_INSTRUMENTS", [])),
                    products=list(yaml_data.get("products", [])),
                    dependencies=list(yaml_data.get("dependencies", [])),
                )

                self.records.append(record)

            except Exception as exc:
                self.errors.append(f"{folder.name}: {exc}")

        self._validate_duplicates()
        return self.records

    def _load_metadata(self, path: Path) -> dict[str, Any]:
        module_name = f"_primenet_metadata_{path.parent.name}"

        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load metadata: {path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        return {
            "OBSERVATORY_ID": getattr(module, "OBSERVATORY_ID", ""),
            "NAME": getattr(module, "NAME", ""),
            "VERSION": getattr(module, "VERSION", ""),
            "CATEGORY": getattr(module, "CATEGORY", ""),
            "AUTHOR": getattr(module, "AUTHOR", ""),
            "DESCRIPTION": getattr(module, "DESCRIPTION", ""),
            "SUPPORTED_INSTRUMENTS": getattr(module, "SUPPORTED_INSTRUMENTS", []),
        }

    def _load_simple_yaml(self, path: Path) -> dict[str, Any]:
        """
        Lightweight YAML reader for PrimeNet observatory.yaml.

        Supports:
        - key: value
        - key: >
          multiline text
        - key:
            - list item
        """

        data: dict[str, Any] = {}
        current_key: str | None = None
        collecting_multiline = False
        multiline_parts: list[str] = []

        lines = path.read_text(encoding="utf-8").splitlines()

        for raw in lines:
            line = raw.rstrip()

            if not line.strip() or line.strip().startswith("#"):
                continue

            stripped = line.strip()

            if collecting_multiline:
                if not raw.startswith(" ") and ":" in stripped:
                    data[current_key] = " ".join(multiline_parts).strip()
                    collecting_multiline = False
                    multiline_parts = []
                    current_key = None
                else:
                    multiline_parts.append(stripped)
                    continue

            if stripped.startswith("- ") and current_key:
                value = stripped[2:].strip()
                if not isinstance(data.get(current_key), list):
                    data[current_key] = []
                data[current_key].append(value)
                continue

            if ":" in stripped:
                key, value = stripped.split(":", 1)
                key = key.strip()
                value = value.strip()

                if value == ">":
                    current_key = key
                    collecting_multiline = True
                    multiline_parts = []
                    continue

                if value == "":
                    data[key] = []
                    current_key = key
                else:
                    data[key] = value
                    current_key = key

        if collecting_multiline and current_key:
            data[current_key] = " ".join(multiline_parts).strip()

        return data

    def _validate_duplicates(self) -> None:
        seen_ids: dict[str, str] = {}
        seen_names: dict[str, str] = {}

        for record in self.records:
            if record.observatory_id:
                if record.observatory_id in seen_ids:
                    self.errors.append(
                        f"Duplicate observatory ID {record.observatory_id}: "
                        f"{seen_ids[record.observatory_id]} and {record.folder}"
                    )
                seen_ids[record.observatory_id] = record.folder

            if record.name:
                if record.name in seen_names:
                    self.errors.append(
                        f"Duplicate observatory name {record.name}: "
                        f"{seen_names[record.name]} and {record.folder}"
                    )
                seen_names[record.name] = record.folder

    def catalog(self) -> list[dict[str, Any]]:
        return [asdict(record) for record in self.records]

    def print_report(self) -> None:
        print("PrimeNet Registry v2")
        print("=" * 60)
        print(f"Root: {self.root}")
        print(f"Observatories directory: {self.observatories_dir}")
        print()

        print(f"Discovered observatories: {len(self.records)}")
        print()

        for record in self.records:
            print("-" * 60)
            print(f"{record.name}")
            print(f"  ID       : {record.observatory_id}")
            print(f"  Folder   : {record.folder}")
            print(f"  Version  : {record.version}")
            print(f"  Category : {record.category}")
            print(f"  Status   : {record.status}")
            print(f"  Class    : {record.observatory_class}")
            print(f"  Instruments: {len(record.supported_instruments)}")
            print(f"  Products   : {len(record.products)}")

        print()

        if self.errors:
            print("Registry warnings/errors:")
            for err in self.errors:
                print(f"  - {err}")
        else:
            print("Registry validation: PASS")

    def save_catalog(self, output_path: str | Path | None = None) -> Path:
        if output_path is None:
            output_path = self.root / "catalog" / "observatory_catalog.json"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(self.catalog(), f, indent=2)

        return output_path


def main() -> None:
    registry = PrimeNetRegistry(root=Path.cwd())
    registry.discover()
    registry.print_report()

    catalog_path = registry.save_catalog()
    print()
    print(f"Wrote observatory catalog: {catalog_path}")


if __name__ == "__main__":
    main()