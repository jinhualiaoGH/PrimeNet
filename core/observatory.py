"""
PrimeNet Observatory Base Interface

Defines the standard lifecycle for all PrimeNet observatories.

Lifecycle:

    prepare()
    measure()
    validate()
    generate_products()
    generate_report()
    run()

Design rule:
    Every observatory should use one shared PrimeNetSession when available.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import json
import time


@dataclass
class ObservatoryResult:
    observatory_id: str
    observatory_name: str
    status: str
    started_at: str
    finished_at: str
    runtime_sec: float
    metrics: dict[str, Any] = field(default_factory=dict)
    products: dict[str, str] = field(default_factory=dict)
    notes: str = ""


class PrimeNetObservatory(ABC):
    """
    Base class for all PrimeNet observatories.

    Preferred usage:

        with PrimeNetSession() as session:
            obs = MyObservatory(session=session)
            obs.run()

    Fallback usage:

        obs = MyObservatory()
        obs.run()

    In fallback mode, the observatory creates its own PrimeNetSession.
    """

    observatory_id: str = "OBS-UNKNOWN"
    observatory_name: str = "Unnamed Observatory"
    observatory_category: str = "general"
    observatory_version: str = "1.0.0"

    def __init__(self, session=None):
        if session is None:
            from core.session import PrimeNetSession
            session = PrimeNetSession(
                session_name=f"{self.observatory_id} {self.observatory_name}"
            )
            self._owns_session = True
        else:
            self._owns_session = False

        self.session = session

        self.config = session.config
        self.paths = session.paths
        self.logger = session.logger
        self.repository = session.repository
        self.products_service = session.products
        self.registry = session.registry

        self.started_at: str | None = None
        self.finished_at: str | None = None
        self.runtime_sec: float | None = None

        self.metrics: dict[str, Any] = {}
        self.products: dict[str, str] = {}
        self.notes: str = ""

    def now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def product_root(self):
        return self.products_service.product_root(
            category=self.observatory_category,
            observatory_id=self.observatory_id,
        )

    def log_identity(self) -> None:
        self.logger.banner(
            f"{self.observatory_id} {self.observatory_name}"
        )
        self.logger.info(f"Category : {self.observatory_category}")
        self.logger.info(f"Version  : {self.observatory_version}")

    @abstractmethod
    def prepare(self) -> None:
        """
        Prepare inputs, files, configuration, and internal state.
        """

    @abstractmethod
    def measure(self) -> None:
        """
        Perform the primary scientific measurement.
        """

    @abstractmethod
    def validate(self) -> None:
        """
        Validate results against expected behavior or known references.
        """

    @abstractmethod
    def generate_products(self) -> None:
        """
        Generate CSV, JSON, figures, or other structured products.
        """

    def generate_report(self) -> None:
        """
        Generate a standard JSON run report.
        """

        report = ObservatoryResult(
            observatory_id=self.observatory_id,
            observatory_name=self.observatory_name,
            status="completed",
            started_at=self.started_at or "",
            finished_at=self.finished_at or "",
            runtime_sec=float(self.runtime_sec or 0.0),
            metrics=self.metrics,
            products=self.products,
            notes=self.notes,
        )

        path = self.products_service.save_json(
            category=self.observatory_category,
            observatory_id=self.observatory_id,
            filename="observatory_run_report.json",
            data=report.__dict__,
        )

        self.products["run_report"] = str(path)

    def run(self) -> ObservatoryResult:
        """
        Execute the standard observatory lifecycle.
        """

        self.started_at = self.now()
        t0 = time.time()

        self.log_identity()

        try:
            self.logger.section("Prepare")
            self.prepare()

            self.logger.section("Measure")
            self.measure()

            self.logger.section("Validate")
            self.validate()

            self.logger.section("Generate Products")
            self.generate_products()

            self.finished_at = self.now()
            self.runtime_sec = time.time() - t0

            self.logger.section("Generate Report")
            self.generate_report()

            self.logger.banner(
                f"{self.observatory_id} completed successfully"
            )

            result = ObservatoryResult(
                observatory_id=self.observatory_id,
                observatory_name=self.observatory_name,
                status="completed",
                started_at=self.started_at,
                finished_at=self.finished_at,
                runtime_sec=self.runtime_sec,
                metrics=self.metrics,
                products=self.products,
                notes=self.notes,
            )

            if self._owns_session:
                self.session.close()

            return result

        except Exception as exc:
            self.finished_at = self.now()
            self.runtime_sec = time.time() - t0

            self.logger.error(
                f"{self.observatory_id} failed: {exc}"
            )

            if self._owns_session:
                self.session.close()

            raise


def main() -> None:
    print("PrimeNet Observatory base interface loaded successfully.")
    print("This module defines the base class for PrimeNet observatories.")
    print("Session-aware observatory interface: ready.")


if __name__ == "__main__":
    main()