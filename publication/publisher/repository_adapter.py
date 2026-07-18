from pathlib import Path
import csv
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
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None

def _try_csv(path):
    try:
        if path.exists():
            with path.open("r", encoding="utf-8", newline="") as stream:
                return list(csv.DictReader(stream))
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
        stats["repository_interval"] = f"{int(range_start):,} <= n <= {int(range_end):,}"
    if total_primes is not None:
        stats["verified_prime_numbers"] = f"{int(total_primes):,}"
    if last_prime is not None:
        stats["largest_stored_prime"] = f"{int(last_prime):,}"
    if partition_count is not None:
        stats["repository_segments"] = str(int(partition_count))
    if partition_size is not None:
        stats["segment_size"] = f"{int(partition_size):,} integers"

    certification = raw.get("certification", {})
    if partition_count is not None and certification.get("all_partitions_sha256_certified"):
        stats["repository_verification"] = f"{int(partition_count)}/{int(partition_count)} passed; SHA-256 certified"

    stats["repository_release_version"] = str(raw.get("repository_release_version", "unknown"))
    stats["repository_release_id"] = str(raw.get("release_id", "unknown"))
    stats["repository_size_gb"] = f"{float(raw['total_size_gb']):,.3f}" if raw.get("total_size_gb") is not None else "unavailable"
    return stats

def _normalize_performance(raw):
    if not raw:
        return {}
    if raw.get("accepted") is not True:
        raise ValueError("Twin-prime performance analysis is not accepted.")

    domain = raw["scientific_domain"]
    accounting = raw["runtime_accounting"]
    windows = {item["name"]: item for item in raw["performance_windows"]}
    steady = windows["conservative_steady_state"]

    return {
        "twin_analysis_id": raw["analysis_id"],
        "twin_analyzer_version": raw["analyzer_version"],
        "twin_numeric_domain": f"{int(domain['numeric_domain_start']):,} – {int(domain['numeric_domain_end']):,}",
        "twin_partitions": str(int(domain["partitions"])),
        "twin_total_gaps": f"{int(domain['total_gaps']):,}",
        "twin_total_events": f"{int(domain['total_twins']):,}",
        "twin_global_density": f"{float(domain['global_twin_density']):.15f}",
        "twin_end_to_end_runtime_sec": f"{float(accounting['summary_end_to_end_runtime_sec']):.6f}",
        "twin_end_to_end_runtime_min": f"{float(accounting['summary_end_to_end_runtime_sec']) / 60.0:.6f}",
        "twin_runtime_accounted_percent": f"{100.0 * float(accounting['partition_runtime_fraction']):.9f}%",
        "steady_partitions": str(int(steady["partitions"])),
        "steady_total_gaps": f"{int(steady['total_gaps']):,}",
        "steady_mean_runtime_sec": f"{float(steady['mean_runtime_sec']):.6f}",
        "steady_median_runtime_sec": f"{float(steady['median_runtime_sec']):.6f}",
        "steady_runtime_cv_percent": f"{100.0 * float(steady['runtime_cv']):.6f}%",
        "steady_p95_runtime_sec": f"{float(steady['p95_runtime_sec']):.6f}",
        "steady_gaps_per_sec": f"{float(steady['sustained_gaps_per_sec']):,.3f}",
    }

def _normalize_theory_validation(raw):
    if not raw or raw.get("status") != "GENERATED":
        return {}

    endpoint = raw.get("final_endpoint", {})
    ratio = float(endpoint["mean_gap_to_log_ratio"])
    mean_gap_rel = ratio - 1.0

    return {
        "theory_validation_status": raw["status"],
        "theory_validation_version": raw.get("version", "unknown"),
        "theory_partition_count": f"{int(raw['partition_count']):,}",
        "theory_domain_start": f"{int(raw['numeric_domain_start']):,}",
        "theory_domain_end": f"{int(raw['numeric_domain_end']):,}",
        "theory_exact_prime_count": f"{int(raw['exact_prime_count']):,}",
        "theory_exact_twin_count": f"{int(raw['exact_twin_count']):,}",
        "theory_terminal_next_prime": f"{int(raw['terminal_next_prime']):,}",
        "theory_endpoint_x": f"{int(endpoint['range_end']):,}",
        "theory_pnt_prediction": f"{float(endpoint['pnt_x_over_log_x']):,.3f}",
        "theory_li_prediction": f"{float(endpoint['li_x']):,.3f}",
        "theory_riemann_r_prediction": f"{float(endpoint['riemann_r_x']):,.3f}",
        "theory_pnt_error_percent": f"{100.0 * float(endpoint['pnt_relative_error']):.9f}%",
        "theory_li_error_percent": f"{100.0 * float(endpoint['li_relative_error']):.9f}%",
        "theory_riemann_r_error_percent": f"{100.0 * float(endpoint['riemann_r_relative_error']):.9f}%",
        "theory_mean_gap": f"{float(endpoint['mean_outgoing_gap']):.12f}",
        "theory_log_midpoint": f"{float(endpoint['log_partition_midpoint']):.12f}",
        "theory_mean_gap_ratio": f"{ratio:.12f}",
        "theory_mean_gap_error_percent": f"{100.0 * mean_gap_rel:.9f}%",
        "theory_hl_prediction": f"{float(endpoint['hardy_littlewood_twin_prediction']):,.3f}",
        "theory_hl_error_percent": f"{100.0 * float(endpoint['hardy_littlewood_twin_relative_error']):.9f}%",
    }

def load_repository_stats(root, config):
    root = Path(root)

    canonical_repository_path = Path(r"E:\PrimeNet\Repository\metadata\repository_statistics.json")
    catalog_repository_path = Path(r"C:\PrimeNet\catalog\repository_summary.json")

    if canonical_repository_path.is_file():
        repository_path = canonical_repository_path
    elif catalog_repository_path.is_file():
        repository_path = catalog_repository_path
    else:
        raise FileNotFoundError(
            "Repository statistics were not found. Checked: "
            f"{canonical_repository_path} and {catalog_repository_path}"
        )

    performance_path = Path(
        r"E:\PrimeNet\Repository\observations\twin_primes"
        r"\twin_prime_performance_analysis.json"
    )
    census_path = Path(
        r"E:\PrimeNet\Repository\observations\twin_primes"
        r"\twin_prime_census_1_3T.csv"
    )
    theory_summary_path = Path(
        r"E:\PrimeNet\Repository\observations\theory_validation"
        r"\theory_validation_summary.json"
    )
    theory_partition_path = Path(
        r"E:\PrimeNet\Repository\observations\theory_validation"
        r"\theory_validation_partition_data.csv"
    )

    repository_raw = _try_json(repository_path)
    if not repository_raw:
        raise FileNotFoundError(f"Canonical repository statistics not found: {repository_path}")

    performance_raw = _try_json(performance_path)
    census_rows = _try_csv(census_path)
    theory_raw = _try_json(theory_summary_path)
    theory_rows = _try_csv(theory_partition_path)

    stats = _normalize_repository(repository_raw)

    if performance_raw:
        stats.update(_normalize_performance(performance_raw))
        stats["_performance_source"] = str(performance_path)
    else:
        stats["_performance_source"] = "unavailable"

    if census_rows:
        stats["_twin_census_rows"] = census_rows
        stats["_twin_census_source"] = str(census_path)
    else:
        stats["_twin_census_rows"] = []
        stats["_twin_census_source"] = "unavailable"

    if not theory_raw:
        raise FileNotFoundError(f"Theory-validation summary not found: {theory_summary_path}")
    if not theory_rows:
        raise FileNotFoundError(f"Theory-validation partition dataset not found: {theory_partition_path}")

    stats.update(_normalize_theory_validation(theory_raw))
    stats["_theory_validation_source"] = str(theory_summary_path)
    stats["_theory_partition_source"] = str(theory_partition_path)
    stats["_theory_partition_rows"] = theory_rows
    stats["_source"] = str(repository_path)
    return stats
