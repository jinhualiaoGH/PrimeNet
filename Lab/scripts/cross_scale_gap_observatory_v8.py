# cross_scale_gap_observatory_v8.py
# PrimeNet Cross-Scale Gap Observatory v8
# Huge-scale raw gap window generator

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
LAB_ROOT = SCRIPT_DIR.parent

CONFIG_DIR = LAB_ROOT / "config"
V7_OUTPUT_DIR = LAB_ROOT / "outputs" / "cross_scale_v7"
V8_OUTPUT_DIR = LAB_ROOT / "outputs" / "cross_scale_v8"

EXPANDED_MANIFEST = CONFIG_DIR / "expanded_cross_scale_manifest.csv"
UPDATED_MANIFEST = CONFIG_DIR / "expanded_cross_scale_manifest_v8.csv"

RAW_WINDOW_DIR = V7_OUTPUT_DIR / "raw_gap_windows"


# =============================================================================
# Prime backend
# =============================================================================

class PrimeBackend:
    def __init__(self) -> None:
        self.backend_name = None
        self.gmpy2 = None
        self.sympy_nextprime = None

        try:
            import gmpy2  # type: ignore
            self.gmpy2 = gmpy2
            self.backend_name = "gmpy2"
            return
        except Exception:
            pass

        try:
            from sympy import nextprime  # type: ignore
            self.sympy_nextprime = nextprime
            self.backend_name = "sympy"
            return
        except Exception:
            pass

        raise RuntimeError(
            "No supported prime backend found. Please install one of:\n"
            "  pip install gmpy2\n"
            "or\n"
            "  pip install sympy\n"
            "Recommended: gmpy2 for huge-number windows."
        )

    def next_prime(self, n: int) -> int:
        if self.backend_name == "gmpy2":
            return int(self.gmpy2.next_prime(n))
        if self.backend_name == "sympy":
            return int(self.sympy_nextprime(n))
        raise RuntimeError("No prime backend available")


# =============================================================================
# Utilities
# =============================================================================

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def parse_scale_value(value) -> int:
    s = str(value).strip()

    if s.startswith("10^"):
        return 10 ** int(s.split("^", 1)[1])

    if s.startswith("1_to_"):
        raise ValueError(f"Baseline scale is not a local huge-window target: {s}")

    return int(float(s))


def existing_gap_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return sum(1 for _ in open(path, "r", encoding="utf-8")) - 1
    except Exception:
        return 0


def write_gap_window(
    backend: PrimeBackend,
    start_n: int,
    window_size: int,
    output_path: Path,
    dataset_id: str,
    resume: bool = True,
    progress_step: int = 10_000,
) -> Dict:
    ensure_dir(output_path.parent)

    existing = existing_gap_count(output_path) if resume else 0

    mode = "a" if resume and output_path.exists() and existing > 0 else "w"

    t0 = time.perf_counter()

    if existing > 0:
        print(f"    [RESUME] existing gaps={existing:,}")
    else:
        print(f"    [START] generating {window_size:,} gaps")

    # Reconstruct current prime position.
    # For simplicity and safety, if resuming, regenerate prime chain to the resume point.
    p = backend.next_prime(start_n)

    for _ in range(existing):
        q = backend.next_prime(p)
        p = q

    generated_now = 0

    with open(output_path, mode, encoding="utf-8", newline="") as f:
        if mode == "w":
            f.write("from_index,to_index,gap\n")

        for i in range(existing, window_size):
            q = backend.next_prime(p)
            gap = q - p

            f.write(f"{i},{i + 1},{gap}\n")

            p = q
            generated_now += 1

            if progress_step > 0 and (i + 1) % progress_step == 0:
                elapsed = time.perf_counter() - t0
                rate = generated_now / max(elapsed, 1e-12)
                print(
                    f"    [PROGRESS] {dataset_id}: "
                    f"{i + 1:,}/{window_size:,} gaps "
                    f"rate={rate:,.1f} gaps/sec"
                )

    runtime = time.perf_counter() - t0

    return {
        "dataset_id": dataset_id,
        "output_path": str(output_path),
        "target_window_size": window_size,
        "existing_before": existing,
        "generated_now": generated_now,
        "final_gap_count": existing + generated_now,
        "runtime_seconds": runtime,
        "rate_gaps_per_second": generated_now / max(runtime, 1e-12),
        "status": "generated" if existing + generated_now >= window_size else "partial",
    }


# =============================================================================
# Main
# =============================================================================

def run_observatory(
    max_datasets: Optional[int] = None,
    only_dataset: Optional[str] = None,
    limit_window: Optional[int] = None,
    resume: bool = True,
) -> None:
    t0 = time.perf_counter()

    ensure_dir(V8_OUTPUT_DIR)
    ensure_dir(RAW_WINDOW_DIR)

    print("=" * 72)
    print("PrimeNet Cross-Scale Gap Observatory v8")
    print("Huge-Scale Raw Gap Window Generator")
    print("=" * 72)
    print(f"Manifest : {EXPANDED_MANIFEST}")
    print(f"Raw dir  : {RAW_WINDOW_DIR}")
    print(f"Output   : {V8_OUTPUT_DIR}")
    print("=" * 72)

    if not EXPANDED_MANIFEST.exists():
        raise FileNotFoundError(f"Expanded manifest not found: {EXPANDED_MANIFEST}")

    manifest = pd.read_csv(EXPANDED_MANIFEST)

    backend = PrimeBackend()
    print(f"Prime backend: {backend.backend_name}")

    targets = manifest[
        (manifest["dataset_type"] == "local_gaps")
        & (manifest["status"].isin(["planned", "partial"]))
    ].copy()

    if only_dataset:
        targets = targets[targets["dataset_id"] == only_dataset]

    if max_datasets is not None:
        targets = targets.head(max_datasets)

    print(f"Targets selected: {len(targets)}")
    print("=" * 72)

    generation_rows: List[Dict] = []

    for idx, row in targets.iterrows():
        dataset_id = str(row["dataset_id"])
        source_path = Path(str(row["source_path"]))

        if not source_path.is_absolute():
            source_path = LAB_ROOT / source_path

        window_size = int(row["window_size"])
        if limit_window is not None:
            window_size = min(window_size, limit_window)

        scale_value = parse_scale_value(row["scale_value"])

        print(f"[DATASET] {dataset_id}")
        print(f"    scale       : {row['coordinate_expression']}")
        print(f"    window_size : {window_size:,}")
        print(f"    output      : {source_path}")

        result = write_gap_window(
            backend=backend,
            start_n=scale_value,
            window_size=window_size,
            output_path=source_path,
            dataset_id=dataset_id,
            resume=resume,
        )

        generation_rows.append(result)

        manifest.loc[manifest["dataset_id"] == dataset_id, "source_path"] = str(source_path)
        manifest.loc[manifest["dataset_id"] == dataset_id, "status"] = result["status"]
        manifest.loc[manifest["dataset_id"] == dataset_id, "notes"] = (
            f"Generated by v8 using {backend.backend_name}; "
            f"gaps={result['final_gap_count']}"
        )

        manifest.to_csv(UPDATED_MANIFEST, index=False)

        print(f"    [DONE] status={result['status']} runtime={result['runtime_seconds']:.3f}s")

    generation_df = pd.DataFrame(generation_rows)

    generation_summary_path = V8_OUTPUT_DIR / "generation_summary.csv"
    generation_df.to_csv(generation_summary_path, index=False)

    final_manifest_copy = V8_OUTPUT_DIR / "expanded_cross_scale_manifest_v8.csv"
    manifest.to_csv(final_manifest_copy, index=False)

    report = {
        "observatory": "PrimeNet Cross-Scale Gap Observatory v8",
        "description": "Huge-scale raw gap window generation for expanded cross-scale campaign",
        "runtime_seconds": time.perf_counter() - t0,
        "prime_backend": backend.backend_name,
        "inputs": {
            "expanded_manifest": str(EXPANDED_MANIFEST),
        },
        "outputs": {
            "updated_manifest": str(UPDATED_MANIFEST),
            "updated_manifest_copy": str(final_manifest_copy),
            "generation_summary": str(generation_summary_path),
            "raw_gap_window_dir": str(RAW_WINDOW_DIR),
            "report": str(V8_OUTPUT_DIR / "observatory_v8_report.json"),
        },
        "targets_selected": int(len(targets)),
        "datasets_generated": int(len(generation_rows)),
        "generated_dataset_ids": [r["dataset_id"] for r in generation_rows],
    }

    with open(V8_OUTPUT_DIR / "observatory_v8_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("=" * 72)
    print("Huge-scale raw gap window generation complete")
    print("=" * 72)
    print(json.dumps(report, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PrimeNet Cross-Scale Gap Observatory v8"
    )

    parser.add_argument(
        "--max-datasets",
        type=int,
        default=None,
        help="Generate only the first N planned datasets.",
    )

    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Generate only one dataset_id.",
    )

    parser.add_argument(
        "--limit-window",
        type=int,
        default=None,
        help="Temporarily cap each window size for testing.",
    )

    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Overwrite instead of resuming existing partial files.",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    run_observatory(
        max_datasets=args.max_datasets,
        only_dataset=args.only,
        limit_window=args.limit_window,
        resume=not args.no_resume,
    )