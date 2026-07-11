import argparse, csv, json, math, statistics
from pathlib import Path
from datetime import datetime

def parse_float(x, default=0.0):
    try: return float(x)
    except Exception: return default

def main():
    ap = argparse.ArgumentParser(description="Analyze PrimeNet generation runtime CSV.")
    ap.add_argument("--runtime-csv", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--anomaly-threshold", type=float, default=30.0)
    ap.add_argument("--critical-threshold", type=float, default=60.0)
    args = ap.parse_args()
    src = Path(args.runtime_csv)
    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(src.open("r", encoding="utf-8-sig", newline="")))
    success = [r for r in rows if r.get("status", "").lower() == "success"]
    for r in success:
        r["runtime_minutes_float"] = parse_float(r.get("runtime_minutes"))
        r["runtime_seconds_float"] = parse_float(r.get("runtime_seconds"))
        r["batch_start_int"] = int(r.get("batch_start", "0") or 0)
        r["batch_end_int"] = int(r.get("batch_end", "0") or 0)
    success.sort(key=lambda r: r["runtime_minutes_float"], reverse=True)
    runtimes = [r["runtime_minutes_float"] for r in success]
    anomalies = [r for r in success if r["runtime_minutes_float"] >= args.anomaly_threshold]
    critical = [r for r in success if r["runtime_minutes_float"] >= args.critical_threshold]
    summary = {
        "analyzed_at": datetime.now().isoformat(timespec="seconds"),
        "runtime_csv": str(src),
        "total_rows": len(rows),
        "success_rows": len(success),
        "skipped_existing_rows": sum(1 for r in rows if r.get("status", "").lower() == "skipped_existing"),
        "failed_rows": sum(1 for r in rows if r.get("status", "").lower() not in ("success", "skipped_existing")),
        "average_runtime_minutes": statistics.mean(runtimes) if runtimes else 0,
        "median_runtime_minutes": statistics.median(runtimes) if runtimes else 0,
        "min_runtime_minutes": min(runtimes) if runtimes else 0,
        "max_runtime_minutes": max(runtimes) if runtimes else 0,
        "anomaly_threshold_minutes": args.anomaly_threshold,
        "critical_threshold_minutes": args.critical_threshold,
        "anomaly_count": len(anomalies),
        "critical_count": len(critical),
        "longest_batch": success[0] if success else None,
    }
    (out/"runtime_analysis_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (out/"runtime_top_batches.csv").open("w", encoding="utf-8", newline="") as f:
        fields = ["rank","timestamp","batch_start","batch_end","runtime_minutes","runtime_seconds","file_size_gb","status","output_file"]
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for i, r in enumerate(success[:25], 1):
            w.writerow({k: r.get(k, "") for k in fields} | {"rank": i})
    with (out/"runtime_anomalies.csv").open("w", encoding="utf-8", newline="") as f:
        fields = ["timestamp","batch_start","batch_end","runtime_minutes","runtime_seconds","file_size_gb","status","output_file"]
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for r in anomalies: w.writerow({k: r.get(k, "") for k in fields})
    md = []
    md.append("# PrimeNet Runtime Analysis\n")
    md.append(f"Source: `{src}`\n")
    md.append(f"Success rows: **{len(success)}**\n")
    md.append(f"Skipped existing rows: **{summary['skipped_existing_rows']}**\n")
    if success:
        top = success[0]
        md.append("## Longest batch\n")
        md.append(f"- Range: **{int(top['batch_start_int']):,} - {int(top['batch_end_int']):,}**\n")
        md.append(f"- Runtime: **{top['runtime_minutes_float']:.6f} minutes** ({top['runtime_seconds_float']:.3f} sec)\n")
        md.append(f"- Output: `{top.get('output_file','')}`\n")
    md.append("\n## Batches above threshold\n")
    if anomalies:
        for r in anomalies:
            md.append(f"- {int(r['batch_start_int']):,} - {int(r['batch_end_int']):,}: {r['runtime_minutes_float']:.6f} min\n")
    else:
        md.append("- None\n")
    md.append("\nRecommended next step: rerun the longest batch in `C:\\PrimeNet\\Lab` output space before changing production code.\n")
    (out/"runtime_analysis_report.md").write_text("".join(md), encoding="utf-8")
    print("Runtime analysis complete.")
    print(f"Longest batch: {summary['longest_batch']['batch_start']} - {summary['longest_batch']['batch_end']} = {summary['max_runtime_minutes']:.6f} min" if success else "No success rows found.")
    print(f"Reports written to: {out}")

if __name__ == "__main__":
    main()
