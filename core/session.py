"""
PrimeNet Session Service
========================

Single entry point for PrimeNet Core services.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import platform
import sys
import uuid

from core.config import Configuration
from core.logger import PrimeNetLogger
from core.paths import Paths
from core.products import ProductService
from core.registry import PrimeNetRegistry
from core.repository import Repository


class PrimeNetSession:
    """PrimeNet runtime session."""

    def __init__(
        self,
        project_root: Path | None = None,
        session_name: str | None = None,
    ) -> None:
        self.session_id = f"SESSION-{uuid.uuid4().hex[:12].upper()}"
        self.session_name = session_name or "PrimeNet Session"
        self.started_at = self.now()
        self.finished_at: str | None = None

        self.config = Configuration(project_root)
        self.paths = Paths(self.config)
        self.project_root = self.paths.project_root
        self.logger = PrimeNetLogger(self.config, self.paths)

        self.repository = Repository(
            config=self.config,
            paths=self.paths,
            logger=self.logger,
        )

        self.products = ProductService(
            config=self.config,
            paths=self.paths,
            logger=self.logger,
        )

        self.registry = PrimeNetRegistry(self.project_root)
        self.registry.discover()

        self.logger.banner("PrimeNet Session Started")
        self.logger.info(f"Session ID   : {self.session_id}")
        self.logger.info(f"Session name : {self.session_name}")
        self.logger.info(f"Project      : {self.config.project_name}")
        self.logger.info(f"Version      : {self.config.project_version}")
        self.logger.info(f"Root         : {self.project_root}")
        self.logger.info(f"Python       : {platform.python_version()}")
        self.logger.info(f"Platform     : {platform.platform()}")
        self.logger.info(
            f"Observatories discovered: {len(self.registry.records)}"
        )

        if self.registry.errors:
            self.logger.info(
                f"Registry warnings/errors: {len(self.registry.errors)}"
            )

    @staticmethod
    def now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def close(self) -> None:
        if self.finished_at is not None:
            return

        self.finished_at = self.now()
        self.logger.banner("PrimeNet Session Finished")
        self.logger.info(f"Session ID : {self.session_id}")
        self.logger.info(f"Started    : {self.started_at}")
        self.logger.info(f"Finished   : {self.finished_at}")

    def summary(self) -> None:
        print("=" * 80)
        print("PrimeNet Session")
        print("=" * 80)
        print(f"Session ID   : {self.session_id}")
        print(f"Session name : {self.session_name}")
        print(f"Project      : {self.config.project_name}")
        print(f"Version      : {self.config.project_version}")
        print(f"Root         : {self.project_root}")
        print()
        print("Core services:")
        print("  config      : ready")
        print("  paths       : ready")
        print("  logger      : ready")
        print("  repository  : ready")
        print("  products    : ready")
        print("  registry    : ready")
        print()
        print(
            f"Observatories discovered: {len(self.registry.records)}"
        )
        print(f"Registry warnings/errors: {len(self.registry.errors)}")
        print("=" * 80)

    def __enter__(self) -> "PrimeNetSession":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if exc_type is not None:
            self.logger.error(
                f"Session exited with error: {exc_value}"
            )
        self.close()


def main() -> int:
    with PrimeNetSession(session_name="Core Session Test") as pn:
        pn.summary()
        pn.registry.print_report()
        pn.repository.summary()
        pn.products.summary()

    return 0


if __name__ == "__main__":
    sys.exit(main())