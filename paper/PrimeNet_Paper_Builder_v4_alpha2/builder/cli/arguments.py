from __future__ import annotations

import argparse

from builder.core.version import __version__


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="primenet-paper",
        description="PrimeNet Paper Builder v4",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("doctor",),
        help="Optional maintenance command",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", help="Path to JSON configuration file")
    parser.add_argument("--project-root", help="PrimeNet paper project root")
    parser.add_argument("--paper", help="Paper plugin name")
    parser.add_argument(
        "--release",
        choices=("preview", "candidate", "final"),
        default=None,
        help="Release channel",
    )
    parser.add_argument(
        "--list-papers",
        action="store_true",
        help="List discovered paper plugins and exit",
    )
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="Allow missing evidence during foundation testing",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser
