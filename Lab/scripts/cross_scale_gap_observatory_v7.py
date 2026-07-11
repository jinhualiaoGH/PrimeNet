# cross_scale_gap_observatory_v7.py
# PrimeNet Cross-Scale Gap Observatory v7
# Expansion campaign builder for systematic cross-scale observations

from __future__ import annotations

import csv
import json
import math
import time
from pathlib import Path
from typing import Dict, List

import pandas as pd


# =============================================================================
# Project paths
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
LAB_ROOT = SCRIPT_DIR.parent

CONFIG_DIR = LAB_ROOT / "config"
OUTPUT_DIR = LAB_ROOT / "outputs" / "cross_scale_v7"

V4_MANIFEST = CONFIG_DIR / "normalized_manifest.csv"
EXPANDED_MANIFEST = CONFIG_DIR / "expanded_cross_scale_manifest.csv"


# =============================================================================
# Campaign configuration
# =============================================================================

# These are observation targets only.
# v7 does not generate primes; it creates a clean reproducible campaign manifest.

BASELINE_DATASETS = [
    {
        "dataset_id": "baseline_1T",
        "dataset_type": "baseline_frequency",
        "coordinate_expression": "1_to_10^12",
        "scale_value": 10**12,
        "window_size": "",
        "log_scale": math.log(10**12),
        "source_path": "",
        "status": "existing",
        "notes": "Baseline aggregated gap frequency distribution to 1T",
    }
]

HUGE_SCALES = [
    "10^50",
    "10^75",
    "10^100",
    "10^150",
    "10^200",
    "10^500",
    "10^1000",
]

WINDOW_SIZES = [
    100_000,
    250_000,
    500_000,
    1_000_000,
]


# =============================================================================
# Utilities
# =============================================================================

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_dataset_id(scale_expr: str, window_size: int) -> str:
    scale_clean = scale_expr.replace("^", "e").replace("+", "")
    if window_size >= 1_000_000:
        w_clean = f"w{window_size // 1_000_000}m"
    elif window_size >= 1_000:
        w_clean = f"w{window_size // 1_000}k"
    else:
        w_clean = f"w{window_size}"

    return f"huge_{scale_clean}_{w_clean}"


def parse_power_of_ten(scale_expr: str) -> int:
    if not scale_expr.startswith("10^"):
        raise ValueError(f"Unsupported scale expression: {scale_expr}")
    return int(scale_expr.split("^", 1)[1])


def expected_source_path(dataset_id: str) -> Path:
    return OUTPUT_DIR / "raw_gap_windows" / f"{dataset_id}_gaps.csv"


def load_existing_manifest(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(path)


def build_campaign_rows() -> List[Dict]:
    rows: List[Dict] = []

    for item in BASELINE_DATASETS:
        rows.append(dict(item))

    for scale_expr in HUGE_SCALES:
        exponent = parse_power_of_ten(scale_expr)
        log_scale = exponent * math.log(10)

        for window_size in WINDOW_SIZES:
            dataset_id = safe_dataset_id(scale_expr, window_size)
            path = expected_source_path(dataset_id)

            rows.append(
                {
                    "dataset_id": dataset_id,
                    "dataset_type": "local_gaps",
                    "coordinate_expression": scale_expr,
                    "scale_value": scale_expr,
                    "window_size": window_size,
                    "log_scale": log_scale,
                    "source_path": str(path),
                    "status": "planned",
                    "notes": "Planned huge-number local prime-gap window",
                }
            )

    return rows


def merge_with_existing_sources(campaign: pd.DataFrame, existing: pd.DataFrame) -> pd.DataFrame:
    if existing.empty:
        return campaign

    existing_cols = set(existing.columns)

    if "dataset_id" not in existing_cols:
        return campaign

    source_col = None
    for candidate in ["source_path", "path"]:
        if candidate in existing_cols:
            source_col = candidate
            break

    if source_col is None:
        return campaign

    existing_map = {
        str(row["dataset_id"]): str(row[source_col])
        for _, row in existing.iterrows()
        if pd.notna(row[source_col])
    }

    for idx, row in campaign.iterrows():
        dataset_id = str(row["dataset_id"])
        if dataset_id in existing_map:
            campaign.at[idx, "source_path"] = existing_map[dataset_id]
            campaign.at[idx, "status"] = "existing"
            campaign.at[idx, "notes"] = "Imported from existing normalized manifest"

    return campaign


def summarize_campaign(df: pd.DataFrame) -> Dict:
    return {
        "total_datasets": int(len(df)),
        "existing_datasets": int((df["status"] == "existing").sum()),
        "planned_datasets": int((df["status"] == "planned").sum()),
        "dataset_types": df["dataset_type"].value_counts().to_dict(),
        "scales": sorted(df["coordinate_expression"].astype(str).unique().tolist()),
        "window_sizes": sorted(
            [
                int(x)
                for x in df["window_size"].dropna().tolist()
                if str(x).strip() != ""
            ]
        ),
    }


def write_generation_plan(df: pd.DataFrame, path: Path) -> None:
    planned = df[df["status"] == "planned"].copy()

    with open(path, "w", encoding="utf-8") as f:
        f.write("# PrimeNet Cross-Scale Gap Observatory v7\n")
        f.write("# Planned huge-window generation commands\n\n")

        f.write("# NOTE:\n")
        f.write("# These commands are templates. Adjust them to match your huge-window\n")
        f.write("# generator script name and arguments if needed.\n\n")

        for _, row in planned.iterrows():
            f.write(f"# {row['dataset_id']}\n")
            f.write(
                "py C:\\PrimeNet\\Lab\\scripts\\huge_window_test.py "
                f"--scale \"{row['coordinate_expression']}\" "
                f"--window-size {row['window_size']} "
                f"--output \"{row['source_path']}\"\n\n"
            )


# =============================================================================
# Main
# =============================================================================

def run_observatory() -> None:
    t0 = time.perf_counter()

    ensure_dir(CONFIG_DIR)
    ensure_dir(OUTPUT_DIR)
    ensure_dir(OUTPUT_DIR / "raw_gap_windows")

    print("=" * 72)
    print("PrimeNet Cross-Scale Gap Observatory v7")
    print("Expansion Campaign Builder")
    print("=" * 72)
    print(f"Existing manifest : {V4_MANIFEST}")
    print(f"Expanded manifest : {EXPANDED_MANIFEST}")
    print(f"Output            : {OUTPUT_DIR}")
    print("=" * 72)

    campaign = pd.DataFrame(build_campaign_rows())

    existing = load_existing_manifest(V4_MANIFEST)
    campaign = merge_with_existing_sources(campaign, existing)

    campaign = campaign.sort_values(
        ["dataset_type", "coordinate_expression", "window_size", "dataset_id"],
        na_position="first",
    ).reset_index(drop=True)

    campaign.to_csv(EXPANDED_MANIFEST, index=False)

    campaign_copy = OUTPUT_DIR / "expanded_cross_scale_manifest.csv"
    campaign.to_csv(campaign_copy, index=False)

    generation_plan = OUTPUT_DIR / "planned_generation_commands.ps1"
    write_generation_plan(campaign, generation_plan)

    summary = summarize_campaign(campaign)

    report = {
        "observatory": "PrimeNet Cross-Scale Gap Observatory v7",
        "description": "Expansion campaign manifest for systematic cross-scale prime-gap observations",
        "runtime_seconds": time.perf_counter() - t0,
        "inputs": {
            "existing_manifest": str(V4_MANIFEST),
        },
        "outputs": {
            "expanded_manifest": str(EXPANDED_MANIFEST),
            "expanded_manifest_copy": str(campaign_copy),
            "generation_plan": str(generation_plan),
            "raw_gap_window_dir": str(OUTPUT_DIR / "raw_gap_windows"),
            "report": str(OUTPUT_DIR / "observatory_v7_report.json"),
        },
        "campaign_summary": summary,
        "next_step": (
            "Generate planned raw gap windows, then rerun v4 using "
            "expanded_cross_scale_manifest.csv or adapt v3/v4 to consume this expanded manifest."
        ),
    }

    report_path = OUTPUT_DIR / "observatory_v7_report.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("=" * 72)
    print("Expansion campaign manifest complete")
    print("=" * 72)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run_observatory()