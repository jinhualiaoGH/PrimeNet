from pathlib import Path
import json
import datetime
from . import __version__

def write_manifest(path, config, stats, figures, tables, review_status, sections=None):
    manifest = {
        "publisher_version": __version__,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "title": config.get("title"),
        "author": config.get("author"),
        "stats_source": stats.get("_source"),
        "performance_source": stats.get("_performance_source"),
        "theory_validation_source": stats.get("_theory_validation_source"),
        "theory_partition_source": stats.get("_theory_partition_source"),
        "repository_interval": stats.get("repository_interval"),
        "verified_prime_numbers": stats.get("verified_prime_numbers"),
        "largest_stored_prime": stats.get("largest_stored_prime"),
        "repository_segments": stats.get("repository_segments"),
        "segment_size": stats.get("segment_size"),
        "repository_release_version": stats.get("repository_release_version"),
        "theory_validation": {
            "status": stats.get("theory_validation_status"),
            "version": stats.get("theory_validation_version"),
            "partition_count": stats.get("theory_partition_count"),
            "domain_start": stats.get("theory_domain_start"),
            "domain_end": stats.get("theory_domain_end"),
            "exact_prime_count": stats.get("theory_exact_prime_count"),
            "exact_twin_count": stats.get("theory_exact_twin_count"),
            "mean_gap_to_log_ratio": stats.get("theory_mean_gap_ratio"),
            "hardy_littlewood_relative_error": stats.get("theory_hl_error_percent"),
        },
        "sections": sections or [],
        "figures": figures,
        "tables": tables,
        "review_status": review_status,
    }
    Path(path).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
