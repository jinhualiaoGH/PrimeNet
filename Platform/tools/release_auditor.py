"""PrimeNet v1.0 release auditor.

Read-only certification checks for the PrimeNet publication candidate.
The auditor never modifies repository assets.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

AUDITOR_VERSION = "1.0.0"
TARGET_PUBLISHER_VERSION = "2.4.2"


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str


def exists(path: Path) -> tuple[bool, str]:
    return path.exists(), str(path)


def nonempty(path: Path) -> tuple[bool, str]:
    ok = path.is_file() and path.stat().st_size > 0
    return ok, f"{path} ({path.stat().st_size:,} bytes)" if ok else str(path)


def valid_json(path: Path) -> tuple[bool, str]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            json.load(handle)
        return True, str(path)
    except Exception as exc:  # diagnostic utility
        return False, f"{path}: {exc}"


def valid_csv(path: Path) -> tuple[bool, str]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader)
        return bool(header), f"{path} ({len(header)} columns)"
    except Exception as exc:
        return False, f"{path}: {exc}"


def publisher_version(path: Path) -> tuple[bool, str]:
    try:
        spec = importlib.util.spec_from_file_location("primenet_publisher_version", path)
        if spec is None or spec.loader is None:
            return False, f"Unable to load {path}"
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        value = getattr(module, "__version__", None)
        return value == TARGET_PUBLISHER_VERSION, f"found {value!r}; expected {TARGET_PUBLISHER_VERSION!r}"
    except Exception as exc:
        return False, f"{path}: {exc}"


def review_passed(path: Path) -> tuple[bool, str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        ok = "Overall Status: PASSED" in text
        return ok, str(path)
    except Exception as exc:
        return False, f"{path}: {exc}"


def git_state(root: Path, require_clean: bool) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["git", "status", "--short"], cwd=root, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if result.returncode != 0:
            return False, result.stderr.strip() or "git status failed"
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            return True, "working tree clean"
        detail = f"{len(lines)} changed/untracked path(s)"
        return (not require_clean), detail
    except Exception as exc:
        return False, str(exc)


def run_check(name: str, function: Callable[[], tuple[bool, str]], optional: bool = False) -> CheckResult:
    try:
        ok, detail = function()
    except Exception as exc:
        ok, detail = False, str(exc)
    if ok:
        status = "PASSED"
    elif optional:
        status = "WARNING"
    else:
        status = "FAILED"
    return CheckResult(name, status, detail)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the PrimeNet v1.0 publication candidate.")
    parser.add_argument("--root", type=Path, default=Path(r"C:\PrimeNet"))
    parser.add_argument("--require-clean-git", action="store_true")
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    root = args.root.resolve()
    publication = root / "publication"
    repository = Path(r"E:\PrimeNet\Repository")
    output = publication / "output"
    theory = repository / "observations" / "theory_validation"

    checks: list[CheckResult] = []
    add = checks.append

    add(run_check("PrimeNet root", lambda: exists(root)))
    add(run_check("Publication source", lambda: exists(publication / "publisher")))
    add(run_check("Publisher version", lambda: publisher_version(publication / "publisher" / "__init__.py")))
    add(run_check("Publication configuration", lambda: nonempty(publication / "publication.yaml")))
    add(run_check("Publication builder", lambda: nonempty(publication / "build_publication.py")))
    add(run_check("Publication verifier", lambda: nonempty(publication / "verify_publication.py")))

    add(run_check("Repository summary", lambda: valid_json(root / "catalog" / "repository_summary.json")))
    add(run_check("Repository inventory", lambda: valid_json(root / "catalog" / "repository_inventory.json"), optional=True))

    add(run_check("Theory-validation summary", lambda: valid_json(theory / "theory_validation_summary.json")))
    add(run_check("Theory-validation partitions", lambda: valid_csv(theory / "theory_validation_partition_data.csv")))

    for number, name in [
        (11, "prime_count_comparison"),
        (12, "prime_count_relative_error"),
        (13, "mean_gap_validation"),
        (13, "mean_gap_ratio"),
        (14, "twin_prime_validation"),
        (14, "twin_prime_relative_error"),
    ]:
        prefix = f"fig{number}{'b' if 'ratio' in name or 'relative_error' in name and number == 14 else ''}_{name}"
        # Use canonical explicit filenames because Figure 13b and 14b are named independently.
    theory_names = [
        "fig11_prime_count_comparison",
        "fig12_prime_count_relative_error",
        "fig13_mean_gap_validation",
        "fig13b_mean_gap_ratio",
        "fig14_twin_prime_validation",
        "fig14b_twin_prime_relative_error",
    ]
    for stem in theory_names:
        add(run_check(f"Theory figure {stem} PNG", lambda stem=stem: nonempty(publication / "figures" / f"{stem}.png")))
        add(run_check(f"Theory figure {stem} SVG", lambda stem=stem: nonempty(publication / "figures" / f"{stem}.svg")))

    add(run_check("Publication DOCX", lambda: nonempty(output / "PrimeNet_Architecture_Publication_Draft_v2_4.docx")))
    add(run_check("Publication review", lambda: review_passed(output / "publication_review_report.txt")))
    add(run_check("Publication manifest", lambda: valid_json(output / "publication_manifest.json")))

    docs = ["README.md", "ARCHITECTURE.md", "CHANGELOG.md", "CITATION.cff", "VERSION"]
    for name in docs:
        add(run_check(f"Documentation {name}", lambda name=name: nonempty(root / name), optional=True))
    add(run_check("Documentation LICENSE", lambda: nonempty(root / "LICENSE"), optional=True))

    add(run_check("Git working tree", lambda: git_state(root, args.require_clean_git), optional=not args.require_clean_git))

    failed = sum(item.status == "FAILED" for item in checks)
    warnings = sum(item.status == "WARNING" for item in checks)
    overall = "CERTIFIED" if failed == 0 and (warnings == 0 or not args.require_clean_git) else "NOT CERTIFIED"

    width = max(len(item.name) for item in checks)
    lines = [
        "PrimeNet Release Audit",
        "=" * 78,
        f"Auditor version : {AUDITOR_VERSION}",
        "Release target  : PrimeNet v1.0 Publication Candidate RC1",
        f"Publisher target: {TARGET_PUBLISHER_VERSION}",
        f"PrimeNet root   : {root}",
        f"Generated UTC   : {datetime.now(timezone.utc).isoformat()}",
        "=" * 78,
    ]
    for item in checks:
        lines.append(f"{item.name:<{width}}  {item.status:7}  {item.detail}")
    lines.extend([
        "=" * 78,
        f"Passed   : {sum(item.status == 'PASSED' for item in checks)}",
        f"Warnings : {warnings}",
        f"Failed   : {failed}",
        f"Overall Status: {overall}",
    ])
    text = "\n".join(lines) + "\n"
    print(text, end="")

    report = args.report or (root / "publication" / "output" / "primenet_v1_release_audit.txt")
    try:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(text, encoding="utf-8")
        print(f"Report: {report}")
    except Exception as exc:
        print(f"WARNING: unable to write report: {exc}", file=sys.stderr)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
