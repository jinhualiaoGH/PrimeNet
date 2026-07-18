from pathlib import Path
import json
import datetime

from . import __version__


def write_manifest(
    path,
    config,
    stats,
    figures,
    tables,
    review_status,
    sections=None,
):
    manifest = {
        "publisher_version": __version__,
        "generated_utc": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",

        "title": config.get("title"),
        "author": config.get("author"),

        "stats_source": stats.get("_source"),
        "performance_source": stats.get("_performance_source"),

        "repository_interval": stats.get("repository_interval"),
        "verified_prime_numbers": stats.get("verified_prime_numbers"),

        # Additional repository metadata (v2.3.1)
        "largest_stored_prime": stats.get("largest_stored_prime"),
        "repository_segments": stats.get("repository_segments"),
        "segment_size": stats.get("segment_size"),
        "repository_release_version": stats.get("repository_release_version"),

        "sections": sections or [],
        "figures": figures,
        "tables": tables,

        "review_status": review_status,
    }

    Path(path).write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    return manifest