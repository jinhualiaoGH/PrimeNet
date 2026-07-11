"""
PrimeNet Lab Commander v1.0

Single-command Lab interface.

Examples:
    py lab.py analyze-runtime
    py lab.py rerun-slowest
    py lab.py rerun-batch 180000000001 190000000000
    py lab.py make-regression-plan
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


DEFAULT_CONFIG = {
    "lab_root": "C:\\PrimeNet\\Lab",
    "platform_root": "C:\\PrimeNet\\Platform",
    "repository_root": "E:\\PrimeNet\\Repository",
    "runtime_csv": "E:\\PrimeNet\\Repository\\logs\\builder_runtime.csv",
    "reports_dir": "C:\\PrimeNet\\Lab\\reports",
    "reruns_dir": "C:\\PrimeNet\\Lab\\reruns",
    "python_executable": "py",
    "builder_module": "core.build_prime_range",
    "anomaly_threshold_minutes": 60.0,
    "critical_threshold_minutes": 30.0
}


def now_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def load_config(config_path: Optional[str]) -> dict:
    path = Path(config_path) if config_path else Path("C:/PrimeNet/Lab/config/lab_config.json")
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
        merged = dict(DEFAULT_CONFIG)
        merged.update(cfg)
        return merged
    return dict(DEFAULT_CONFIG)


def ensure_dirs(cfg: dict) -> None:
    for key in ["reports_dir", "reruns_dir"]:
        Path(cfg[key]).mkdir(parents=True, exist_ok=True)


def read_runtime_csv(runtime_csv: str) -> list[dict]:
    path = Path(runtime_csv)
    if not path.exists():
        raise FileNotFoundError(f"Runtime CSV not found: {path}")

    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip rows that do not have real generation runtime.
            status = (row.get("status") or "").strip().lower()
            if status and status not in {"success", "completed", "ok", "passed"}:
                # Keep generated rows only. skipped_existing should not define slowest generation.
                if status == "skipped_existing":
                    continue
            try:
                row["_runtime_minutes"] = float(row.get("runtime_minutes", "nan"))
            except Exception:
                try:
                    row["_runtime_minutes"] = float(row.get("runtime_seconds", "nan")) / 60.0
                except Exception:
                    continue

            try:
                row["_batch_start"] = int(str(row.get("batch_start", "")).replace(",", ""))
                row["_batch_end"] = int(str(row.get("batch_end", "")).replace(",", ""))
            except Exception:
                # tolerate alternative field names
                continue

            rows.append(row)

    return rows


def analyze_runtime(cfg: dict, top_n: int = 10) -> dict:
    rows = read_runtime_csv(cfg["runtime_csv"])
    if not rows:
        raise RuntimeError("No generated batch runtime rows found.")

    rows_sorted = sorted(rows, key=lambda r: r["_runtime_minutes"], reverse=True)
    runtimes = [r["_runtime_minutes"] for r in rows]

    avg = sum(runtimes) / len(runtimes)
    median = sorted(runtimes)[len(runtimes) // 2] if len(runtimes) % 2 else (
        sorted(runtimes)[len(runtimes)//2 - 1] + sorted(runtimes)[len(runtimes)//2]
    ) / 2.0

    report = {
        "generated_batches": len(rows),
        "average_runtime_minutes": avg,
        "median_runtime_minutes": median,
        "min_runtime_minutes": min(runtimes),
        "max_runtime_minutes": max(runtimes),
        "slowest": {
            "batch_start": rows_sorted[0]["_batch_start"],
            "batch_end": rows_sorted[0]["_batch_end"],
            "runtime_minutes": rows_sorted[0]["_runtime_minutes"],
            "output_file": rows_sorted[0].get("output_file", "")
        },
        "top_slowest": [
            {
                "rank": i + 1,
                "batch_start": r["_batch_start"],
                "batch_end": r["_batch_end"],
                "runtime_minutes": r["_runtime_minutes"],
                "output_file": r.get("output_file", "")
            }
            for i, r in enumerate(rows_sorted[:top_n])
        ],
        "over_critical_threshold": [
            {
                "batch_start": r["_batch_start"],
                "batch_end": r["_batch_end"],
                "runtime_minutes": r["_runtime_minutes"],
                "output_file": r.get("output_file", "")
            }
            for r in rows_sorted
            if r["_runtime_minutes"] >= float(cfg["critical_threshold_minutes"])
        ],
        "over_anomaly_threshold": [
            {
                "batch_start": r["_batch_start"],
                "batch_end": r["_batch_end"],
                "runtime_minutes": r["_runtime_minutes"],
                "output_file": r.get("output_file", "")
            }
            for r in rows_sorted
            if r["_runtime_minutes"] >= float(cfg["anomaly_threshold_minutes"])
        ],
    }

    out_dir = Path(cfg["reports_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "runtime_analysis_latest.json"
    txt_path = out_dir / "runtime_analysis_latest.txt"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    with txt_path.open("w", encoding="utf-8") as f:
        f.write("PrimeNet Lab Runtime Analysis\n")
        f.write("=" * 70 + "\n")
        f.write(f"Generated batches: {report['generated_batches']}\n")
        f.write(f"Average runtime:   {report['average_runtime_minutes']:.6f} min\n")
        f.write(f"Median runtime:    {report['median_runtime_minutes']:.6f} min\n")
        f.write(f"Min runtime:       {report['min_runtime_minutes']:.6f} min\n")
        f.write(f"Max runtime:       {report['max_runtime_minutes']:.6f} min\n\n")
        f.write("Slowest batch\n")
        f.write("-" * 70 + "\n")
        s = report["slowest"]
        f.write(f"{s['batch_start']} - {s['batch_end']} = {s['runtime_minutes']:.6f} min\n\n")
        f.write("Top slowest batches\n")
        f.write("-" * 70 + "\n")
        for item in report["top_slowest"]:
            f.write(
                f"{item['rank']:02d}. {item['batch_start']} - {item['batch_end']} "
                f"= {item['runtime_minutes']:.6f} min\n"
            )
        f.write("\nBatches over critical threshold\n")
        f.write("-" * 70 + "\n")
        for item in report["over_critical_threshold"]:
            f.write(f"{item['batch_start']} - {item['batch_end']} = {item['runtime_minutes']:.6f} min\n")

    print("Runtime analysis complete.")
    print(f"Generated batches: {report['generated_batches']}")
    print(f"Slowest batch: {s['batch_start']} - {s['batch_end']} = {s['runtime_minutes']:.6f} min")
    print(f"Reports written to: {out_dir}")
    return report


def write_lab_notebook_entry(cfg: dict, title: str, content: str) -> Path:
    nb_dir = Path(cfg["lab_root"]) / "notebook"
    nb_dir.mkdir(parents=True, exist_ok=True)
    path = nb_dir / f"{now_id()}_{title.lower().replace(' ', '_')}.md"
    path.write_text(content, encoding="utf-8")
    return path


def rerun_batch(cfg: dict, start: int, end: int, overwrite: bool = True, dry_run: bool = False) -> None:
    run_id = f"rerun_{start}_{end}_{now_id()}"
    rerun_dir = Path(cfg["reruns_dir"]) / run_id
    output_dir = rerun_dir / "ranges"
    logs_dir = rerun_dir / "logs"
    metadata_dir = rerun_dir / "metadata"
    for d in [output_dir, logs_dir, metadata_dir]:
        d.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"primes_{start}_{end}.npy"
    runtime_csv = logs_dir / "runtime.csv"

    # This command assumes the existing builder module supports CLI start/end/output arguments.
    # If your current builder uses different argument names, we will adjust this after the first dry-run.
    cmd = [
        cfg["python_executable"],
        "-m",
        cfg["builder_module"],
        "--start", str(start),
        "--end", str(end),
        "--output", str(output_file),
        "--runtime-csv", str(runtime_csv),
    ]
    if overwrite:
        cmd.append("--overwrite")

    command_txt = " ".join(f'"{x}"' if " " in x else x for x in cmd)
    (metadata_dir / "command.txt").write_text(command_txt, encoding="utf-8")

    print("PrimeNet Lab rerun-batch")
    print("=" * 70)
    print(f"Range:      {start} - {end}")
    print(f"Rerun dir:  {rerun_dir}")
    print(f"Output:     {output_file}")
    print(f"Command:    {command_txt}")

    if dry_run:
        print("\nDRY RUN ONLY. No batch was executed.")
        return

    started = datetime.now()
    proc = subprocess.run(cmd, cwd=cfg["platform_root"])
    finished = datetime.now()

    summary = {
        "run_id": run_id,
        "batch_start": start,
        "batch_end": end,
        "started": started.isoformat(),
        "finished": finished.isoformat(),
        "return_code": proc.returncode,
        "output_file": str(output_file),
        "runtime_csv": str(runtime_csv),
    }
    (metadata_dir / "rerun_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    nb = write_lab_notebook_entry(
        cfg,
        "LAB rerun batch",
        f"""# LAB Rerun Batch

Run ID: `{run_id}`

Range: `{start} - {end}`

Started: `{started.isoformat()}`

Finished: `{finished.isoformat()}`

Return code: `{proc.returncode}`

Output file: `{output_file}`

Command:

```powershell
{command_txt}
```
"""
    )

    print("=" * 70)
    print(f"Return code: {proc.returncode}")
    print(f"Notebook entry: {nb}")


def rerun_slowest(cfg: dict, dry_run: bool = False) -> None:
    report = analyze_runtime(cfg)
    start = int(report["slowest"]["batch_start"])
    end = int(report["slowest"]["batch_end"])
    print()
    print("Rerunning slowest batch...")
    rerun_batch(cfg, start, end, dry_run=dry_run)


def make_regression_plan(cfg: dict) -> None:
    batches = [
        (1, 10_000_000_000),
        (40_000_000_001, 50_000_000_000),
        (90_000_000_001, 100_000_000_000),
        (180_000_000_001, 190_000_000_000),
        (300_000_000_001, 310_000_000_000),
        (490_000_000_001, 500_000_000_000),
        (600_000_000_001, 610_000_000_000),
        (750_000_000_001, 760_000_000_000),
        (900_000_000_001, 910_000_000_000),
        (990_000_000_001, 1_000_000_000_000),
    ]
    out_dir = Path(cfg["reports_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "ten_batch_regression_plan.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["rank", "batch_start", "batch_end", "purpose"])
        for i, (s, e) in enumerate(batches, start=1):
            purpose = "standard"
            if s == 180_000_000_001:
                purpose = "known runtime anomaly"
            elif s == 990_000_000_001:
                purpose = "final repository boundary"
            elif s == 1:
                purpose = "initial repository boundary"
            writer.writerow([i, s, e, purpose])
    print(f"Regression plan written to: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="PrimeNet Lab Commander")
    parser.add_argument("--config", default=None, help="Path to lab_config.json")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("analyze-runtime")

    p_batch = sub.add_parser("rerun-batch")
    p_batch.add_argument("start", type=int)
    p_batch.add_argument("end", type=int)
    p_batch.add_argument("--dry-run", action="store_true")

    p_slowest = sub.add_parser("rerun-slowest")
    p_slowest.add_argument("--dry-run", action="store_true")

    sub.add_parser("make-regression-plan")

    args = parser.parse_args()
    cfg = load_config(args.config)
    ensure_dirs(cfg)

    if args.command == "analyze-runtime":
        analyze_runtime(cfg)
    elif args.command == "rerun-batch":
        rerun_batch(cfg, args.start, args.end, dry_run=args.dry_run)
    elif args.command == "rerun-slowest":
        rerun_slowest(cfg, dry_run=args.dry_run)
    elif args.command == "make-regression-plan":
        make_regression_plan(cfg)


if __name__ == "__main__":
    main()
