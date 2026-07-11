from __future__ import annotations

import csv
import json
import statistics
from datetime import datetime
from pathlib import Path
from core.platform_config import load_platform_config


CONFIG = load_platform_config()
PATHS = CONFIG.paths

ROOT = PATHS.repository_root
RUNTIME_CSV = PATHS.logs_dir / "builder_runtime.csv"
META = PATHS.metadata_dir

SUMMARY_JSON = META / "repository_runtime_summary.json"
SUMMARY_CSV = META / "repository_runtime_summary.csv"
PERFORMANCE_JSON = META / "repository_performance.json"


def f(x):
    try:
        return float(x)
    except Exception:
        return None


def i(x):
    try:
        return int(float(x))
    except Exception:
        return None


def parse_rows():
    rows = []

    with RUNTIME_CSV.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.reader(fp)
        header = next(reader, None)

        for raw in reader:
            if not raw:
                continue

            # New v2 row format, appended after old header:
            # timestamp,big_batch_index,total_big_batches,output_batch_index,
            # total_output_batches,start,end,runtime_sec,runtime_min,
            # file_exists,file_size_gb,return_code,status,...
            if len(raw) >= 13 and raw[12].strip().upper() == "PASSED":
                rows.append(
                    {
                        "timestamp": raw[0],
                        "batch_id": i(raw[3]),
                        "total_batches": i(raw[4]),
                        "start": i(raw[5]),
                        "end": i(raw[6]),
                        "runtime_sec": f(raw[7]),
                        "runtime_min": f(raw[8]),
                        "file_size_gb": f(raw[10]),
                        "status": raw[12],
                    }
                )
                continue

            # Old v1.2 row format:
            # run_id,timestamp,batch_id,total_batches,...,
            # file_size_gb,runtime_seconds,runtime_minutes,status,...
            if len(raw) >= 12 and raw[11].strip().lower() == "passed":
                rows.append(
                    {
                        "timestamp": raw[1],
                        "batch_id": i(raw[2]),
                        "total_batches": i(raw[3]),
                        "start": i(raw[5]),
                        "end": i(raw[6]),
                        "runtime_sec": f(raw[9]),
                        "runtime_min": f(raw[10]),
                        "file_size_gb": f(raw[8]),
                        "status": raw[11],
                    }
                )

    return [r for r in rows if r["runtime_min"] and r["runtime_min"] > 0]


def main():
    print("=" * 80)
    print("PrimeNet Runtime Summarizer v1.2.0")
    print("=" * 80)

    rows = parse_rows()

    if not rows:
        raise RuntimeError("No successful runtime rows found.")

    runtimes = [r["runtime_min"] for r in rows]
    sizes = [r["file_size_gb"] for r in rows if r["file_size_gb"] is not None]

    fastest = min(rows, key=lambda r: r["runtime_min"])
    slowest = max(rows, key=lambda r: r["runtime_min"])

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "runtime_csv": str(RUNTIME_CSV),
        "successful_rows": len(rows),
        "total_runtime_min_sum_of_batches": sum(runtimes),
        "total_runtime_hours_sum_of_batches": sum(runtimes) / 60,
        "average_runtime_min": statistics.mean(runtimes),
        "median_runtime_min": statistics.median(runtimes),
        "min_runtime_min": min(runtimes),
        "max_runtime_min": max(runtimes),
        "std_runtime_min": statistics.stdev(runtimes) if len(runtimes) > 1 else 0,
        "repository_size_gb_from_runtime_log": sum(sizes),
        "average_partition_size_gb": statistics.mean(sizes),
        "fastest_batch": fastest,
        "slowest_batch": slowest,
    }

    META.mkdir(parents=True, exist_ok=True)

    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    PERFORMANCE_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    with SUMMARY_CSV.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["metric", "value"])
        for k, v in summary.items():
            writer.writerow([k, json.dumps(v) if isinstance(v, dict) else v])

    print(f"[OK] Successful rows : {len(rows)}")
    print(f"[OK] Wrote           : {SUMMARY_JSON}")
    print(f"[OK] Wrote           : {SUMMARY_CSV}")
    print(f"[OK] Updated         : {PERFORMANCE_JSON}")
    print()
    print(f"Average runtime : {summary['average_runtime_min']:.3f} min")
    print(f"Median runtime  : {summary['median_runtime_min']:.3f} min")
    print(f"Fastest runtime : {summary['min_runtime_min']:.3f} min")
    print(f"Slowest runtime : {summary['max_runtime_min']:.3f} min")
    print("=" * 80)


if __name__ == "__main__":
    main()