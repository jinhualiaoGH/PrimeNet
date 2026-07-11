"""
PrimeNet Product Service

Standardized output manager for all PrimeNet observatories.

Design rule:
    Observatories should not write files directly.
    They should use the Product Service whenever possible.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Any
import csv
import json

from core.config import Configuration
from core.paths import Paths
from core.logger import PrimeNetLogger


class ProductService:
    """
    Standard product/output service for PrimeNet.
    """

    def __init__(
        self,
        config: Configuration,
        paths: Paths,
        logger: PrimeNetLogger | None = None,
    ):
        self.config = config
        self.paths = paths
        self.logger = logger

    def _log(self, message: str) -> None:
        if self.logger is not None:
            self.logger.info(message)
        else:
            print(message)

    def now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def product_root(
        self,
        category: str,
        observatory_id: str,
    ) -> Path:
        path = (
            self.paths.project_root
            / "products"
            / "results"
            / category
            / observatory_id.lower()
        )
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_json(
        self,
        category: str,
        observatory_id: str,
        filename: str,
        data: dict[str, Any],
    ) -> Path:
        path = self.product_root(category, observatory_id) / filename
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._log(f"Wrote JSON: {path}")
        return path

    def save_csv(
        self,
        category: str,
        observatory_id: str,
        filename: str,
        rows: list[dict[str, Any]],
        fieldnames: list[str] | None = None,
    ) -> Path:
        path = self.product_root(category, observatory_id) / filename

        if fieldnames is None:
            if rows:
                fieldnames = list(rows[0].keys())
            else:
                fieldnames = []

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        self._log(f"Wrote CSV: {path}")
        return path

    def save_text(
        self,
        category: str,
        observatory_id: str,
        filename: str,
        text: str,
    ) -> Path:
        path = self.product_root(category, observatory_id) / filename
        path.write_text(text, encoding="utf-8")
        self._log(f"Wrote text: {path}")
        return path

    def save_markdown(
        self,
        category: str,
        observatory_id: str,
        filename: str,
        markdown: str,
    ) -> Path:
        if not filename.endswith(".md"):
            filename += ".md"
        return self.save_text(category, observatory_id, filename, markdown)

    def save_manifest(
        self,
        category: str,
        observatory_id: str,
        products: dict[str, str],
        metrics: dict[str, Any] | None = None,
    ) -> Path:
        manifest = {
            "project": "PrimeNet",
            "created_at": self.now(),
            "category": category,
            "observatory_id": observatory_id,
            "products": products,
            "metrics": metrics or {},
        }

        return self.save_json(
            category=category,
            observatory_id=observatory_id,
            filename="product_manifest.json",
            data=manifest,
        )

    def summary(self) -> None:
        print("=" * 80)
        print("PrimeNet Product Service")
        print("=" * 80)
        print(f"Products root: {self.paths.project_root / 'products'}")
        print(f"Results root : {self.paths.project_root / 'products' / 'results'}")
        print("=" * 80)


def main() -> None:
    cfg = Configuration()
    paths = Paths(cfg)
    logger = PrimeNetLogger(cfg, paths)

    products = ProductService(cfg, paths, logger)
    products.summary()

    demo = {
        "project": "PrimeNet",
        "service": "ProductService",
        "status": "working",
        "created_at": products.now(),
    }

    products.save_json(
        category="core_test",
        observatory_id="product-service",
        filename="product_service_test.json",
        data=demo,
    )


if __name__ == "__main__":
    main()
