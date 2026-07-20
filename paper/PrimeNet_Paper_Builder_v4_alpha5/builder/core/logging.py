from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(log_root: Path, *, verbose: bool = False) -> Path:
    log_root.mkdir(parents=True, exist_ok=True)
    log_file = log_root / "paper_builder.log"
    level = logging.DEBUG if verbose else logging.INFO

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root.addHandler(console)
    root.addHandler(file_handler)
    return log_file
