from pathlib import Path
import json


DEFAULT_STATS = {
    "repository_interval": "unavailable",
    "verified_prime_numbers": "unavailable",
    "largest_stored_prime": "unavailable",
    "repository_segments": "unavailable",
    "segment_size": "unavailable",
    "repository_verification": "unavailable",
    "repository_construction": "Deterministic",
    "prime_space": "Implemented",
    "observatory_framework": "Implemented",
    "product_framework": "Implemented",
    "registry_services": "Implemented",
}


def _try_json(path):
    try:
        if path.exists():
            return json.loads(
                path.read_text(encoding="utf-8")
            )
    except Exception:
        return None

    return None


def _normalize_repository(raw):
    stats = DEFAULT_STATS.copy()

    if not raw:
        return stats

    range_start = raw.get("range_start")
    range_end = raw.get("range_end")
    total_primes = raw.get("total_primes")
    last_prime = raw.get("last_prime")
    partition_count = raw.get("partition_count")
    partition_size = raw.get("partition_size_nominal")

    if range_start is not None and range_end is not None:
        stats["repository_interval"] = (
            f"{int(range_start):,} <= n <= "
            f"{int(range_end):,}"
        )

    if total_primes is not None:
        stats["verified_prime_numbers"] = (
            f"{int(total_primes):,}"
        )

    if last_prime is not None:
        stats["largest_stored_prime"] = (
            f"{int(last_prime):,}"
        )

    if partition_count is not None:
        stats["repository_segments"] = str(
            int(partition_count)
        )

    if partition_size is not None:
        stats["segment_size"] = (
            f"{int(partition_size):,} integers"
        )

    certification = raw.get("certification", {})

    if (
        partition_count is not None
        and certification.get(
            "all_partitions_sha256_certified"
        )
    ):
        stats["repository_verification"] = (
            f"{int(partition_count)}/"
            f"{int(partition_count)} passed; "
            "SHA-256 certified"
        )

    stats["repository_release_version"] = str(
        raw.get("repository_release_version", "unknown")
    )

    stats["repository_release_id"] = str(
        raw.get("release_id", "unknown")
    )

    stats["repository_size_gb"] = (
        f"{float(raw['total_size_gb']):,.3f}"
        if raw.get("total_size_gb") is not None
        else "unavailable"
    )

    return stats


def _normalize_performance(raw):
    if not raw:
        return {}

    if raw.get("accepted") is not True:
        raise ValueError(
            "Twin-prime performance analysis is not accepted."
        )

    domain = raw["scientific_domain"]
    accounting = raw["runtime_accounting"]

    windows = {
        item["name"]: item
        for item in raw["performance_windows"]
    }

    steady = windows["conservative_steady_state"]

    return {
        "twin_analysis_id": raw["analysis_id"],
        "twin_analyzer_version": raw["analyzer_version"],
        "twin_numeric_domain": (
            f"{int(domain['numeric_domain_start']):,} – "
            f"{int(domain['numeric_domain_end']):,}"
        ),
        "twin_partitions": str(
            int(domain["partitions"])
        ),
        "twin_total_gaps": (
            f"{int(domain['total_gaps']):,}"
        ),
        "twin_total_events": (
            f"{int(domain['total_twins']):,}"
        ),
        "twin_global_density": (
            f"{float(domain['global_twin_density']):.15f}"
        ),
        "twin_end_to_end_runtime_sec": (
            f"{float(
                accounting[
                    'summary_end_to_end_runtime_sec'
                ]
            ):.6f}"
        ),
        "twin_end_to_end_runtime_min": (
            f"{float(
                accounting[
                    'summary_end_to_end_runtime_sec'
                ]
            ) / 60.0:.6f}"
        ),
        "twin_runtime_accounted_percent": (
            f"{100.0 * float(
                accounting['partition_runtime_fraction']
            ):.9f}%"
        ),
        "steady_partitions": str(
            int(steady["partitions"])
        ),
        "steady_total_gaps": (
            f"{int(steady['total_gaps']):,}"
        ),
        "steady_mean_runtime_sec": (
            f"{float(steady['mean_runtime_sec']):.6f}"
        ),
        "steady_median_runtime_sec": (
            f"{float(steady['median_runtime_sec']):.6f}"
        ),
        "steady_runtime_cv_percent": (
            f"{100.0 * float(steady['runtime_cv']):.6f}%"
        ),
        "steady_p95_runtime_sec": (
            f"{float(steady['p95_runtime_sec']):.6f}"
        ),
        "steady_gaps_per_sec": (
            f"{float(
                steady['sustained_gaps_per_sec']
            ):,.3f}"
        ),
    }


def load_repository_stats(root, config):
    root = Path(root)

    repository_path = Path(
        r"E:\PrimeNet\Repository\metadata"
        r"\repository_statistics.json"
    )

    performance_path = Path(
        r"E:\PrimeNet\Repository\observations"
        r"\twin_primes"
        r"\twin_prime_performance_analysis.json"
    )

    repository_raw = _try_json(repository_path)

    if not repository_raw:
        raise FileNotFoundError(
            "Canonical repository statistics not found: "
            f"{repository_path}"
        )

    performance_raw = _try_json(performance_path)

    if not performance_raw:
        raise FileNotFoundError(
            "Accepted twin-prime performance analysis "
            f"not found: {performance_path}"
        )

    stats = _normalize_repository(repository_raw)
    stats.update(
        _normalize_performance(performance_raw)
    )

    stats["_source"] = str(repository_path)
    stats["_performance_source"] = str(
        performance_path
    )

    return stats
