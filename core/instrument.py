"""
PrimeNet Instrument Base Interface

An Instrument is the measurement unit of PrimeNet.

Observatory = scientific program
Instrument  = measurement method
Product     = saved result
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import time


@dataclass
class InstrumentResult:
    instrument_id: str
    instrument_name: str
    status: str
    started_at: str
    finished_at: str
    runtime_sec: float
    metrics: dict[str, Any] = field(default_factory=dict)
    products: dict[str, str] = field(default_factory=dict)
    notes: str = ""


class PrimeNetInstrument(ABC):
    """
    Base class for PrimeNet measurement instruments.
    """

    instrument_id: str = "INST-UNKNOWN"
    instrument_name: str = "Unnamed Instrument"
    instrument_category: str = "general"
    instrument_version: str = "1.0.0"

    def __init__(self, session=None) -> None:
        self.session = session

        if session is not None:
            self.config = session.config
            self.paths = session.paths
            self.logger = session.logger
            self.products_service = session.products
        else:
            self.config = None
            self.paths = None
            self.logger = None
            self.products_service = None

        self.started_at: str | None = None
        self.finished_at: str | None = None
        self.runtime_sec: float | None = None

        self.metrics: dict[str, Any] = {}
        self.products: dict[str, str] = {}
        self.notes: str = ""

    def now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def log(self, message: str) -> None:
        if self.logger is not None:
            self.logger.info(message)
        else:
            print(message)

    def log_identity(self) -> None:
        self.log("=" * 72)
        self.log(f"{self.instrument_id} {self.instrument_name}")
        self.log(f"Category : {self.instrument_category}")
        self.log(f"Version  : {self.instrument_version}")
        self.log("=" * 72)

    @abstractmethod
    def prepare(self) -> None:
        """
        Prepare instrument inputs.
        """

    @abstractmethod
    def measure(self) -> None:
        """
        Execute the instrument measurement.
        """

    @abstractmethod
    def validate(self) -> None:
        """
        Validate instrument output.
        """

    @abstractmethod
    def generate_products(self) -> None:
        """
        Save instrument products.
        """

    def run(self) -> InstrumentResult:
        """
        Execute the standard instrument lifecycle.
        """

        self.started_at = self.now()
        t0 = time.time()

        self.log_identity()

        try:
            self.log("Prepare")
            self.prepare()

            self.log("Measure")
            self.measure()

            self.log("Validate")
            self.validate()

            self.log("Generate Products")
            self.generate_products()

            self.finished_at = self.now()
            self.runtime_sec = time.time() - t0

            result = InstrumentResult(
                instrument_id=self.instrument_id,
                instrument_name=self.instrument_name,
                status="completed",
                started_at=self.started_at,
                finished_at=self.finished_at,
                runtime_sec=self.runtime_sec,
                metrics=self.metrics,
                products=self.products,
                notes=self.notes,
            )

            self.log(f"{self.instrument_id} completed successfully.")
            return result

        except Exception as exc:
            self.finished_at = self.now()
            self.runtime_sec = time.time() - t0
            self.log(f"{self.instrument_id} failed: {exc}")
            raise


def main() -> None:
    print("PrimeNetInstrument base class loaded successfully.")
    print("This module defines shared infrastructure for measurement instruments.")


if __name__ == "__main__":
    main()