import argparse, csv, json
from pathlib import Path
from datetime import datetime

def batch_ranges(start, end, batch_size):
    s = start
    while s <= end:
        e = min(s + batch_size - 1, end)
        yield s, e
        s = e + 1

def read_longest(runtime_csv):
    p = Path(runtime_csv)
    if not p.exists(): return None
    rows = list(csv.DictReader(p.open("r", encoding="utf-8-sig", newline="")))
    best = None
    for r in rows:
        if r.get("status", "").lower() != "success": continue
        try: m = float(r.get("runtime_minutes", "0"))
        except Exception: continue
        if best is None or m > best[0]: best = (m, int(r["batch_start"]), int(r["batch_end"]))
    return best

def main():
    ap = argparse.ArgumentParser(description="Create PrimeNet 10-batch Lab regression plan.")
    ap.add_argument("--runtime-csv", default="")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=10**12)
    ap.add_argument("--batch-size", type=int, default=10_000_000_000)
    args = ap.parse_args()
    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    ranges = list(batch_ranges(args.start, args.end, args.batch_size))
    n = len(ranges)
    selected_indices = {0, 4, 9, 34, 49, 64, 89, 94, 98, 99}
    longest = read_longest(args.runtime_csv) if args.runtime_csv else None
    notes = {}
    if longest:
        _, s, e = longest
        try:
            idx = ranges.index((s, e))
            selected_indices.add(idx)
            notes[idx] = "longest observed runtime batch"
        except ValueError:
            pass
    selected = []
    for idx in sorted(i for i in selected_indices if 0 <= i < n):
        s, e = ranges[idx]
        selected.append({
            "batch_number": idx + 1,
            "batch_start": s,
            "batch_end": e,
            "expected_filename": f"primes_{s}_{e}.npy",
            "reason": notes.get(idx, "representative coverage")
        })
    plan = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "name": "PrimeNet Lab 10-batch regression plan",
        "repository_start": args.start,
        "repository_end": args.end,
        "batch_size": args.batch_size,
        "selected_count": len(selected),
        "selected_batches": selected,
        "notes": "Run these in Lab output space, not in official repository ranges. Include the longest observed batch when available."
    }
    (out/"regression_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    with (out/"regression_plan.csv").open("w", encoding="utf-8", newline="") as f:
        fields = ["batch_number","batch_start","batch_end","expected_filename","reason"]
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(selected)
    ps = []
    ps.append("# PrimeNet Lab regression commands template\n")
    ps.append("# Adjust the builder command if your Lab builder CLI differs.\n")
    ps.append("$LabOutput = \"C:\\PrimeNet\\Lab\\outputs\\regression_runs\"\n")
    ps.append("if (!(Test-Path $LabOutput)) { New-Item -ItemType Directory -Path $LabOutput | Out-Null }\n")
    for b in selected:
        ps.append(f"# Batch {b['batch_number']}: {b['batch_start']} - {b['batch_end']} ({b['reason']})\n")
        ps.append(f"# py -m core.build_prime_range --start {b['batch_start']} --end {b['batch_end']} --output-dir $LabOutput --overwrite\n")
    (out/"regression_commands_template.ps1").write_text("".join(ps), encoding="utf-8")
    print(f"Regression plan written to {out}")
    if longest:
        print(f"Included longest observed batch: {longest[1]} - {longest[2]} = {longest[0]:.6f} min")

if __name__ == "__main__": main()
