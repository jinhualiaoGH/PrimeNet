"""
PrimeNet Logger Service

Shared logging service for the PrimeNet platform.

Design principles
-----------------
- One logger per PrimeNet session
- Console + file logging
- Log directory managed by Path Service
- Configuration-driven
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from core.config import Configuration
from core.paths import Paths


class PrimeNetLogger:
    """
    Shared PrimeNet logging service.
    """

    def __init__(
        self,
        config: Configuration,
        paths: Paths,
        name: str = "PrimeNet",
    ):

        self.config = config
        self.paths = paths

        self.paths.ensure_runtime_directories()

        log_level_name = (
            self.config.logging.get("level", "INFO").upper()
        )

        level = getattr(logging, log_level_name, logging.INFO)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.log_file = (
            self.paths.logs /
            f"primenet_{timestamp}.log"
        )

        self.logger = logging.getLogger(name)

        self.logger.setLevel(level)

        # Avoid duplicate handlers if instantiated twice
        if self.logger.handlers:
            return

        formatter = logging.Formatter(
            "[%(asctime)s] "
            "[%(levelname)-8s] "
            "%(message)s",
            "%Y-%m-%d %H:%M:%S",
        )

        # Console
        console = logging.StreamHandler()
        console.setFormatter(formatter)

        # File
        file_handler = logging.FileHandler(
            self.log_file,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)

        self.logger.addHandler(console)
        self.logger.addHandler(file_handler)

    # -----------------------------------------------------

    def debug(self, message: str):
        self.logger.debug(message)

    def info(self, message: str):
        self.logger.info(message)

    def warning(self, message: str):
        self.logger.warning(message)

    def error(self, message: str):
        self.logger.error(message)

    def critical(self, message: str):
        self.logger.critical(message)

    # -----------------------------------------------------

    def banner(self, title: str):

        line = "=" * 80

        self.info("")
        self.info(line)
        self.info(title)
        self.info(line)

    # -----------------------------------------------------

    def section(self, title: str):

        self.info("")
        self.info("-" * 80)
        self.info(title)
        self.info("-" * 80)

    # -----------------------------------------------------

    @property
    def logfile(self) -> Path:
        return self.log_file


def main():

    cfg = Configuration()

    paths = Paths(cfg)

    logger = PrimeNetLogger(cfg, paths)

    logger.banner("PrimeNet Logger Service")

    logger.info("Logger initialized successfully.")

    logger.info(f"Log file: {logger.logfile}")

    logger.section("Example Messages")

    logger.debug("Debug message")

    logger.info("Information message")

    logger.warning("Warning message")

    logger.error("Error message")

    logger.critical("Critical message")


if __name__ == "__main__":

    main()
