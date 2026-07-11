import argparse, csv, json, time
from pathlib import Path
from datetime import datetime

def expected_ranges(start, end, batch_size):
    s = start
    while s <= end:
        e = min(s + batch_size - 1, end)
        yield s, e, f"primes_{s}_{e}.npy"
        s = e + 1

def verify_file(path, prev_last=None):
    import numpy as np
    arr = np.load(path, mmap_mode="r")
    if arr.size == 0:
        return False, {"error":"empty array"}, prev_last
    first = int(arr[0]); last = int(arr[-1])
    if prev_last is not None and first <= prev_last:
        return False, {"error":f"boundary not strictly increasing: previous_last={prev_last}, current_first={first}", "first":first, "last":last, "count":int(arr.size)}, last
    # local monotonicity check without loading all into memory if possible
    chunk = 5_000_000
    prev = None
    min_gap = None
    max_gap = None
    for i in range(0, arr.size, chunk):
        part = arr[i:i+chunk]
        if len(part) == 0: continue
        if prev is not None:
            g = int(part[0]) - int(prev)
            min_gap = g if min_gap is None else min(min_gap, g)
            max_gap = g if max_gap is None else max(max_gap, g)
            if g <= 0:
                return False, {"error":"non-increasing across internal chunk boundary", "first":first, "last":last, "count":int(arr.size)}, last
        if len(part) > 1:
            d = np.diff(part)
            if (d <= 0).any():
                return False, {"error":"local array not strictly increasing", "first":first, "last":last, "count":int(arr.size)}, last
            mn = int(d.min()); mx = int(d.max())
            min_gap = mn if min_gap is None else min(min_gap, mn)
            max_gap = mx if max_gap is None else max(max_gap, mx)
        prev = int(part[-1])
    return True, {"error":"", "count":int(arr.size), "first":first, "last":last, "min_gap":min_gap, "max_gap":max_gap}, last

def main():
    ap = argparse.ArgumentParser(description="Verify only expected PrimeNet repository files and report extra legacy files separately.")
    ap.add_argument("--ranges-dir", required=True)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=10**12)
    ap.add_argument("--batch-size", type=int, default=10_000_000_000)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--no-array-check", action="store_true", help="Only check names/existence; do not load npy arrays.")
    args = ap.parse_args()
    t0 = time.time()
    ranges_dir = Path(args.ranges_dir)
    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    expected = list(expected_ranges(args.start, args.end, args.batch_size))
    expected_names = {name for _,_,name in expected}
    actual_names = {p.name for p in ranges_dir.glob("primes_*.npy")}
    extra = sorted(actual_names - expected_names)
    missing = sorted(expected_names - actual_names)
    results = []
    passed = 0; failed = 0; prev_last = None
    if not missing:
        for idx, (s, e, name) in enumerate(expected, 1):
            path = ranges_dir / name
            rec = {"index":idx,"file":name,"expected_start":s,"expected_end":e,"exists":path.exists(),"passed":False,"error":""}
            if not path.exists():
                rec["error"] = "missing file"; failed += 1
            elif args.no_array_check:
                rec["passed"] = True; passed += 1
            else:
                try:
                    ok, details, prev_last = verify_file(path, prev_last)
                    rec.update(details); rec["passed"] = ok
                    passed += 1 if ok else 0; failed += 0 if ok else 1
                except Exception as ex:
                    rec["error"] = repr(ex); failed += 1
            results.append(rec)
    else:
        failed = len(missing)
    status = "PASS" if failed == 0 and len(missing) == 0 else "FAILED"
    summary = {
        "verified_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "ranges_dir": str(ranges_dir),
        "expected_files": len(expected),
        "found_expected_files": len(expected_names & actual_names),
        "extra_files": len(extra),
        "missing_files": len(missing),
        "passed_files": passed,
        "failed_files": failed,
        "runtime_seconds": time.time() - t0,
        "extra_file_list": extra,
        "missing_file_list": missing,
        "note": "Extra files are reported but are not treated as official repository members."
    }
    (out/"expected_file_verification_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (out/"expected_file_verification_results.csv").open("w", encoding="utf-8", newline="") as f:
        fields = ["index","file","expected_start","expected_end","exists","passed","count","first","last","min_gap","max_gap","error"]
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for r in results: w.writerow({k:r.get(k,"") for k in fields})
    lines = ["PrimeNet Expected File Verification\n", "===================================\n\n"]
    for k in ["status","expected_files","found_expected_files","extra_files","missing_files","passed_files","failed_files","runtime_seconds"]:
        lines.append(f"{k}: {summary[k]}\n")
    lines.append("\nExtra files:\n")
    lines.extend([f"- {x}\n" for x in extra] or ["- None\n"])
    lines.append("\nMissing files:\n")
    lines.extend([f"- {x}\n" for x in missing] or ["- None\n"])
    (out/"expected_file_verification_report.txt").write_text("".join(lines), encoding="utf-8")
    print(f"Status: {status}")
    print(f"Expected: {len(expected)}, found expected: {len(expected_names & actual_names)}, extra: {len(extra)}, missing: {len(missing)}, passed: {passed}, failed: {failed}")
    print(f"Reports written to: {out}")

if __name__ == "__main__": main()
