"""
PrimeNet Platform Core
======================

Canonical repository construction, verification, physical access,
index-coordinate querying, configuration, and operational reporting.

Public APIs should be imported explicitly from their owning modules.

Examples
--------
    from Platform.core.platform_config import load_platform_config

    from Platform.core.repository import (
        PrimeRepository,
        GapRepository,
    )

    from Platform.core.query_repository import (
        PrimeQueryRepository,
    )

Importing Platform.core itself performs no configuration loading,
repository discovery, file access, or write operations.
"""

from __future__ import annotations


__all__: tuple[str, ...] = ()