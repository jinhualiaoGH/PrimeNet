"""
PrimeNet Architecture Acceptance Audit v1.1.0

Read-only audit of the active PrimeNet architecture.

Run:
    cd C:\\PrimeNet
    py -B -m maintenance.audit_primenet_architecture
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


VERSION = "1.1.0"

PRIMENET_ROOT = Path(r"C:\PrimeNet")
REPOSITORY_ROOT = Path(r"E:\PrimeNet\Repository")
REPORT_DIR = PRIMENET_ROOT / "reports" / "architecture_acceptance"
JSON_REPORT = REPORT_DIR / "primenet_architecture_audit.json"
TEXT_REPORT = REPORT_DIR / "primenet_architecture_audit.txt"

ACTIVE_SOURCE_ROOTS = [
    PRIMENET_ROOT / "core",
    PRIMENET_ROOT / "Platform" / "core",
    PRIMENET_ROOT / "instruments",
    PRIMENET_ROOT / "observatories",
    PRIMENET_ROOT / "maintenance",
]

REQUIRED_DIRECTORIES = [
    PRIMENET_ROOT / "core",
    PRIMENET_ROOT / "core" / "execution",
    PRIMENET_ROOT / "Platform",
    PRIMENET_ROOT / "Platform" / "core",
    PRIMENET_ROOT / "Platform" / "config",
    PRIMENET_ROOT / "instruments",
    PRIMENET_ROOT / "observatories",
    PRIMENET_ROOT / "observatories" / "twin_primes",
    PRIMENET_ROOT / "maintenance",
    PRIMENET_ROOT / "paper",
    PRIMENET_ROOT / "products",
    PRIMENET_ROOT / "reports",
    PRIMENET_ROOT / "runs",
    REPOSITORY_ROOT,
    REPOSITORY_ROOT / "ranges",
    REPOSITORY_ROOT / "gaps",
    REPOSITORY_ROOT / "metadata",
    REPOSITORY_ROOT / "observations" / "twin_primes",
]

REQUIRED_FILES = [
    PRIMENET_ROOT / "README.md",
    PRIMENET_ROOT / "ARCHITECTURE.md",
    PRIMENET_ROOT / "VERSION",
    PRIMENET_ROOT / ".gitignore",
    PRIMENET_ROOT / "core" / "__init__.py",
    PRIMENET_ROOT / "core" / "config.py",
    PRIMENET_ROOT / "core" / "instrument.py",
    PRIMENET_ROOT / "core" / "logger.py",
    PRIMENET_ROOT / "core" / "mission.py",
    PRIMENET_ROOT / "core" / "observatory.py",
    PRIMENET_ROOT / "core" / "observatory_factory.py",
    PRIMENET_ROOT / "core" / "paths.py",
    PRIMENET_ROOT / "core" / "products.py",
    PRIMENET_ROOT / "core" / "registry.py",
    PRIMENET_ROOT / "core" / "repository.py",
    PRIMENET_ROOT / "core" / "session.py",
    PRIMENET_ROOT / "core" / "execution" / "primenet_job_runner.py",
    PRIMENET_ROOT / "Platform" / "__init__.py",
    PRIMENET_ROOT / "Platform" / "core" / "__init__.py",
    PRIMENET_ROOT / "Platform" / "core" / "build_prime_range.py",
    PRIMENET_ROOT / "Platform" / "core" / "drive_prime_repository.py",
    PRIMENET_ROOT / "Platform" / "core" / "verify_repository.py",
    PRIMENET_ROOT / "Platform" / "core" / "build_gap_repository.py",
    PRIMENET_ROOT / "Platform" / "core" / "verify_gap_repository.py",
    PRIMENET_ROOT / "Platform" / "core" / "range_files.py",
    PRIMENET_ROOT / "Platform" / "core" / "repository.py",
    PRIMENET_ROOT / "Platform" / "core" / "query_repository.py",
    PRIMENET_ROOT / "Platform" / "core" / "finalize_repository.py",
    PRIMENET_ROOT / "Platform" / "core" / "summarize_runtime.py",
    PRIMENET_ROOT / "observatories" / "__init__.py",
    PRIMENET_ROOT / "observatories" / "twin_primes" / "__init__.py",
    PRIMENET_ROOT / "observatories" / "twin_primes" / "count_twins.py",
    PRIMENET_ROOT / "observatories" / "twin_primes" / "validation_package" / "README.md",
    REPOSITORY_ROOT / "metadata" / "gap_repository_manifest.csv",
    REPOSITORY_ROOT / "observations" / "twin_primes" / "twin_prime_census_1_3T.csv",
    REPOSITORY_ROOT / "observations" / "twin_primes" / "twin_prime_census_1_3T_summary.json",
]

SUPERSEDED_ACTIVE_NAMES = {
    "build_gap_events.py",
    "build_gap_sequences.py",
    "build_prime_events.py",
    "drive_gap_event_repository.py",
    "drive_prime_event_repository.py",
    "drive_gap_sequence_repository.py",
    "drive_gap_repository.py",
    "optimize_gap_repository.py",
    "drive_prime_repository_100B.py",
    "verify_gap_events.py",
    "verify_gap_sequences.py",
    "verify_prime_events.py",
    "build_gap_repository_u16_from_primes.py",
    "build_gap_repository_u16_from_primes_v3.py",
    "verify_gap_repository_u16.py",
    "check_gap_boundary_contract.py",
    "repository_pipeline_v2.py",
    "run_repository_full_test.py",
}

SUPERSEDED_TEXT_PATTERNS = [
    r"core\.build_gap_repository_u16_from_primes",
    r"core\.verify_gap_repository_u16",
    r"core\.repository_pipeline_v2",
    r"core\.build_gap_sequences",
    r"core\.drive_gap_sequence_repository",
    r"gaps_u16_direct",
]

MALFORMED_IMPORT_PATTERNS = [
    re.compile(r"^\s*fromcore\."),
    re.compile(r"^\s*importcore\."),
    re.compile(r"^\s*fromPlatform\."),
    re.compile(r"^\s*importPlatform\."),
    re.compile(r"^\s*fromobservatories\."),
    re.compile(r"^\s*importobservatories\."),
    re.compile(r"^\s*frominstruments\."),
    re.compile(r"^\s*importinstruments\."),
]

EXPECTED_PRIME_FILE_COUNT = 300
EXPECTED_GAP_FILE_COUNT = 300
EXPECTED_TOTAL_PRIMES = 108_340_298_703
EXPECTED_TOTAL_GAPS = 108_340_298_703
EXPECTED_TWIN_EVENTS = 5_173_760_785
EXPECTED_TWIN_DENSITY = 0.04775472143734025


@dataclass
class AuditCheck:
    name: str
    category: str
    passed: bool
    expected: str
    observed: str
    details: str = ""


def fmt_int(value: int) -> str:
    return f"{value:,}"


def add_check(
    checks: list[AuditCheck],
    *,
    name: str,
    category: str,
    passed: bool,
    expected: object,
    observed: object,
    details: str = "",
) -> None:
    checks.append(
        AuditCheck(
            name=name,
            category=category,
            passed=bool(passed),
            expected=str(expected),
            observed=str(observed),
            details=details,
        )
    )


def relative_display(path: Path) -> str:
    try:
        return str(path.relative_to(PRIMENET_ROOT))
    except ValueError:
        return str(path)


def iter_python_files(roots: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file() and root.suffix == ".py":
            files.append(root)
            continue
        files.extend(
            path for path in root.rglob("*.py")
            if "archive" not in path.parts
        )
    return sorted(set(files))


def iter_text_files() -> list[Path]:
    suffixes = {
        ".py", ".md", ".yaml", ".yml", ".json",
        ".ps1", ".txt", ".toml",
    }

    active_roots = [
        PRIMENET_ROOT / "core",
        PRIMENET_ROOT / "Platform",
        PRIMENET_ROOT / "instruments",
        PRIMENET_ROOT / "observatories",
        PRIMENET_ROOT / "maintenance",
        PRIMENET_ROOT / "README.md",
        PRIMENET_ROOT / "ARCHITECTURE.md",
        PRIMENET_ROOT / "CONTRIBUTING.md",
        PRIMENET_ROOT / "CODE_OF_CONDUCT.md",
        PRIMENET_ROOT / "CITATION.cff",
        PRIMENET_ROOT / "manifest.json",
    ]

    files: list[Path] = []

    for root in active_roots:
        if not root.exists():
            continue

        if root.is_file():
            if (
                root.suffix.lower() in suffixes
                and root.resolve() != Path(__file__).resolve()
            ):
                files.append(root)
            continue

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            if "archive" in path.parts:
                continue

            if path.resolve() == Path(__file__).resolve():
                continue

            if path.suffix.lower() in suffixes:
                files.append(path)

    return sorted(set(files))


def parse_numeric_range(path: Path, prefix: str) -> tuple[int, int]:
    pattern = re.compile(
        rf"^{re.escape(prefix)}_(\d+)_(\d+)\.npy$"
    )
    match = pattern.match(path.name)
    if not match:
        raise ValueError(f"Invalid range filename: {path.name}")

    start = int(match.group(1))
    end = int(match.group(2))

    if start > end:
        raise ValueError(f"Range start exceeds end: {path.name}")

    return start, end


def sorted_numeric_range_files(directory: Path, prefix: str) -> list[Path]:
    files = list(directory.glob(f"{prefix}_*.npy"))
    return sorted(files, key=lambda path: parse_numeric_range(path, prefix))


def run_subprocess(
    command: list[str],
    *,
    cwd: Path,
    timeout: int = 300,
) -> tuple[int, str, str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=environment,
    )

    return (
        completed.returncode,
        completed.stdout.strip(),
        completed.stderr.strip(),
    )


def check_required_directories(checks: list[AuditCheck]) -> None:
    for path in REQUIRED_DIRECTORIES:
        add_check(
            checks,
            name=f"directory:{relative_display(path)}",
            category="filesystem",
            passed=path.is_dir(),
            expected="directory exists",
            observed="exists" if path.is_dir() else "missing",
        )


def check_required_files(checks: list[AuditCheck]) -> None:
    for path in REQUIRED_FILES:
        add_check(
            checks,
            name=f"file:{relative_display(path)}",
            category="filesystem",
            passed=path.is_file(),
            expected="file exists",
            observed="exists" if path.is_file() else "missing",
        )


def check_superseded_active_modules(checks: list[AuditCheck]) -> None:
    found: list[str] = []
    for root in ACTIVE_SOURCE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if "archive" in path.parts:
                continue
            if path.name in SUPERSEDED_ACTIVE_NAMES:
                found.append(relative_display(path))

    add_check(
        checks,
        name="superseded_modules_absent",
        category="architecture",
        passed=not found,
        expected="no superseded modules in active source tree",
        observed="none" if not found else ", ".join(found),
        details="\n".join(found),
    )


def check_python_syntax(checks: list[AuditCheck]) -> None:
    failures: list[str] = []
    python_files = iter_python_files(ACTIVE_SOURCE_ROOTS)

    for path in python_files:
        try:
            source = path.read_text(encoding="utf-8-sig")
            ast.parse(source, filename=str(path))
            compile(source, str(path), "exec")
        except Exception as exc:
            failures.append(
                f"{relative_display(path)}: "
                f"{type(exc).__name__}: {exc}"
            )

    add_check(
        checks,
        name="active_python_parse_and_compile",
        category="syntax",
        passed=not failures,
        expected=f"{len(python_files)} Python files parse and compile",
        observed=(
            f"{len(python_files)} passed"
            if not failures else f"{len(failures)} failures"
        ),
        details="\n".join(failures),
    )


def check_malformed_imports(checks: list[AuditCheck]) -> None:
    failures: list[str] = []

    for path in iter_python_files(ACTIVE_SOURCE_ROOTS):
        lines = path.read_text(
            encoding="utf-8-sig",
            errors="replace",
        ).splitlines()

        for number, line in enumerate(lines, start=1):
            if any(pattern.search(line) for pattern in MALFORMED_IMPORT_PATTERNS):
                failures.append(
                    f"{relative_display(path)}:{number}: {line}"
                )

    add_check(
        checks,
        name="malformed_imports_absent",
        category="imports",
        passed=not failures,
        expected="no malformed import statements",
        observed="none" if not failures else f"{len(failures)} found",
        details="\n".join(failures),
    )


def check_platform_namespace_imports(checks: list[AuditCheck]) -> None:
    failures: list[str] = []
    platform_core = PRIMENET_ROOT / "Platform" / "core"

    if platform_core.exists():
        for path in platform_core.glob("*.py"):
            lines = path.read_text(
                encoding="utf-8-sig",
                errors="replace",
            ).splitlines()

            for number, line in enumerate(lines, start=1):
                stripped = line.strip()
                if stripped.startswith("from core."):
                    failures.append(
                        f"{relative_display(path)}:{number}: {line}"
                    )
                elif stripped.startswith("import core."):
                    failures.append(
                        f"{relative_display(path)}:{number}: {line}"
                    )

    add_check(
        checks,
        name="platform_import_namespace",
        category="imports",
        passed=not failures,
        expected="Platform modules use explicit Platform.core imports",
        observed="compliant" if not failures else f"{len(failures)} violations",
        details="\n".join(failures),
    )


def check_canonical_imports(checks: list[AuditCheck]) -> None:
    import_script = """
import Platform.core.build_gap_repository
import Platform.core.verify_gap_repository
import Platform.core.verify_repository
import Platform.core.query_repository
import core.execution.primenet_job_runner
import core.instrument
import core.observatory
import core.repository
import observatories.twin_primes.count_twins
import instruments.transition.transition_matrix_instrument
print("PrimeNet canonical imports passed.")
""".strip()

    try:
        code, stdout, stderr = run_subprocess(
            [sys.executable, "-B", "-c", import_script],
            cwd=PRIMENET_ROOT,
            timeout=180,
        )

        passed = (
            code == 0
            and "PrimeNet canonical imports passed." in stdout
        )

        details = "\n".join(
            part for part in [stdout, stderr] if part
        )

        add_check(
            checks,
            name="canonical_module_imports",
            category="imports",
            passed=passed,
            expected="all canonical modules import successfully",
            observed="passed" if passed else f"return code {code}",
            details=details,
        )

    except subprocess.TimeoutExpired:
        add_check(
            checks,
            name="canonical_module_imports",
            category="imports",
            passed=False,
            expected="imports complete within 180 seconds",
            observed="timeout",
        )


def check_generated_cache_artifacts(checks: list[AuditCheck]) -> None:
    pycache_dirs: list[str] = []
    pyc_files: list[str] = []

    for root in [
        PRIMENET_ROOT / "core",
        PRIMENET_ROOT / "Platform",
        PRIMENET_ROOT / "observatories",
        PRIMENET_ROOT / "instruments",
        PRIMENET_ROOT / "maintenance",
    ]:
        if not root.exists():
            continue

        for path in root.rglob("__pycache__"):
            if "archive" not in path.parts:
                pycache_dirs.append(relative_display(path))

        for path in root.rglob("*.pyc"):
            if "archive" not in path.parts:
                pyc_files.append(relative_display(path))

    all_artifacts = pycache_dirs + pyc_files

    add_check(
        checks,
        name="generated_cache_artifacts_absent",
        category="cleanliness",
        passed=not all_artifacts,
        expected="no active __pycache__ directories or .pyc files",
        observed=(
            "none" if not all_artifacts
            else f"{len(all_artifacts)} artifacts"
        ),
        details="\n".join(all_artifacts),
    )


def check_gitignore(checks: list[AuditCheck]) -> None:
    path = PRIMENET_ROOT / ".gitignore"

    if not path.exists():
        add_check(
            checks,
            name="gitignore_python_cache_rules",
            category="cleanliness",
            passed=False,
            expected="__pycache__/ and *.pyc exclusions",
            observed=".gitignore missing",
        )
        return

    text = path.read_text(
        encoding="utf-8-sig",
        errors="replace",
    )

    has_pycache = "__pycache__/" in text or "__pycache__" in text
    has_pyc = "*.pyc" in text or "*.py[cod]" in text

    add_check(
        checks,
        name="gitignore_python_cache_rules",
        category="cleanliness",
        passed=has_pycache and has_pyc,
        expected="contains __pycache__/ and Python bytecode rule",
        observed=f"__pycache__={has_pycache}, bytecode={has_pyc}",
    )


def check_obsolete_text_references(checks: list[AuditCheck]) -> None:
    findings: list[str] = []
    compiled_patterns = [re.compile(pattern) for pattern in SUPERSEDED_TEXT_PATTERNS]

    for path in iter_text_files():
        try:
            lines = path.read_text(
                encoding="utf-8-sig",
                errors="replace",
            ).splitlines()
        except OSError:
            continue

        for number, line in enumerate(lines, start=1):
            if any(pattern.search(line) for pattern in compiled_patterns):
                findings.append(
                    f"{relative_display(path)}:{number}: {line.strip()}"
                )

    add_check(
        checks,
        name="obsolete_active_references_absent",
        category="documentation",
        passed=not findings,
        expected="no active references to superseded pipelines",
        observed="none" if not findings else f"{len(findings)} found",
        details="\n".join(findings),
    )


def check_numeric_repository_order(checks: list[AuditCheck]) -> None:
    prime_dir = REPOSITORY_ROOT / "ranges"
    gap_dir = REPOSITORY_ROOT / "gaps"

    prime_failures: list[str] = []
    gap_failures: list[str] = []

    try:
        prime_files = sorted_numeric_range_files(prime_dir, "primes")
    except Exception as exc:
        prime_files = []
        prime_failures.append(str(exc))

    try:
        gap_files = sorted_numeric_range_files(gap_dir, "gaps")
    except Exception as exc:
        gap_files = []
        gap_failures.append(str(exc))

    for label, files, failures in [
        ("prime", prime_files, prime_failures),
        ("gap", gap_files, gap_failures),
    ]:
        previous_end: int | None = None

        for path in files:
            try:
                start, end = parse_numeric_range(
                    path,
                    "primes" if label == "prime" else "gaps",
                )
            except Exception as exc:
                failures.append(str(exc))
                continue

            if previous_end is not None and start != previous_end + 1:
                failures.append(
                    f"{path.name}: expected start "
                    f"{previous_end + 1}, observed {start}"
                )

            previous_end = end

    add_check(
        checks,
        name="prime_repository_numeric_order",
        category="repository",
        passed=(
            len(prime_files) == EXPECTED_PRIME_FILE_COUNT
            and not prime_failures
        ),
        expected=(
            f"{EXPECTED_PRIME_FILE_COUNT} numerically ordered "
            "contiguous prime files"
        ),
        observed=(
            f"{len(prime_files)} files, "
            f"{len(prime_failures)} issues"
        ),
        details="\n".join(prime_failures),
    )

    add_check(
        checks,
        name="gap_repository_numeric_order",
        category="repository",
        passed=(
            len(gap_files) == EXPECTED_GAP_FILE_COUNT
            and not gap_failures
        ),
        expected=(
            f"{EXPECTED_GAP_FILE_COUNT} numerically ordered "
            "contiguous gap files"
        ),
        observed=(
            f"{len(gap_files)} files, "
            f"{len(gap_failures)} issues"
        ),
        details="\n".join(gap_failures),
    )


def check_repository_acceptance_summary(checks: list[AuditCheck]) -> None:
    path = (
        PRIMENET_ROOT
        / "observatories"
        / "twin_primes"
        / "validation_package"
        / "validation"
        / "repository_acceptance_summary.json"
    )

    if not path.exists():
        add_check(
            checks,
            name="repository_acceptance_provenance",
            category="repository",
            passed=False,
            expected="repository acceptance summary exists",
            observed="missing",
        )
        return

    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        add_check(
            checks,
            name="repository_acceptance_provenance",
            category="repository",
            passed=False,
            expected="valid repository acceptance JSON",
            observed=f"invalid: {exc}",
        )
        return

    conditions = [
        data.get("acceptance_status") == "ACCEPTED",
        int(data.get("prime_files", -1)) == EXPECTED_PRIME_FILE_COUNT,
        int(data.get("gap_files", -1)) == EXPECTED_GAP_FILE_COUNT,
        int(data.get("total_primes", -1)) == EXPECTED_TOTAL_PRIMES,
        int(data.get("total_gaps", -1)) == EXPECTED_TOTAL_GAPS,
        int(data.get("ordinary_boundaries_verified", -1)) == 299,
        int(data.get("terminal_boundaries_verified", -1)) == 1,
        int(data.get("warnings", -1)) == 0,
        int(data.get("errors", -1)) == 0,
    ]

    add_check(
        checks,
        name="repository_acceptance_provenance",
        category="repository",
        passed=all(conditions),
        expected=(
            "ACCEPTED; 300 prime files; 300 gap files; "
            "108,340,298,703 primes/gaps; 0 errors"
        ),
        observed=(
            f"status={data.get('acceptance_status')}, "
            f"prime_files={data.get('prime_files')}, "
            f"gap_files={data.get('gap_files')}, "
            f"total_primes={data.get('total_primes')}, "
            f"total_gaps={data.get('total_gaps')}, "
            f"errors={data.get('errors')}"
        ),
    )


def check_twin_census_summary(checks: list[AuditCheck]) -> None:
    path = (
        REPOSITORY_ROOT
        / "observations"
        / "twin_primes"
        / "twin_prime_census_1_3T_summary.json"
    )

    if not path.exists():
        add_check(
            checks,
            name="twin_prime_census_summary",
            category="observatory",
            passed=False,
            expected="Twin Prime Census summary exists",
            observed="missing",
        )
        return

    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        add_check(
            checks,
            name="twin_prime_census_summary",
            category="observatory",
            passed=False,
            expected="valid census summary JSON",
            observed=f"invalid: {exc}",
        )
        return

    observed_density = float(data.get("global_twin_density", float("nan")))

    conditions = [
        data.get("repository_status") == "ACCEPTED",
        int(data.get("gap_files_scanned", -1)) == EXPECTED_GAP_FILE_COUNT,
        int(data.get("total_gaps_scanned", -1)) == EXPECTED_TOTAL_GAPS,
        int(data.get("total_twin_prime_events", -1)) == EXPECTED_TWIN_EVENTS,
        abs(observed_density - EXPECTED_TWIN_DENSITY) <= 1e-15,
    ]

    add_check(
        checks,
        name="twin_prime_census_summary",
        category="observatory",
        passed=all(conditions),
        expected=(
            f"{fmt_int(EXPECTED_TWIN_EVENTS)} twin events, "
            f"density {EXPECTED_TWIN_DENSITY:.15f}"
        ),
        observed=(
            f"twins={data.get('total_twin_prime_events')}, "
            f"density={observed_density:.15f}, "
            f"status={data.get('repository_status')}"
        ),
    )


def check_validation_package_checksums(checks: list[AuditCheck]) -> None:
    package_dir = (
        PRIMENET_ROOT
        / "observatories"
        / "twin_primes"
        / "validation_package"
    )
    sums_path = package_dir / "SHA256SUMS.txt"

    if not sums_path.exists():
        add_check(
            checks,
            name="twin_validation_checksum_manifest",
            category="observatory",
            passed=False,
            expected="SHA256SUMS.txt exists",
            observed="missing",
        )
        return

    entries = [
        line
        for line in sums_path.read_text(
            encoding="utf-8-sig",
            errors="replace",
        ).splitlines()
        if line.strip()
    ]

    add_check(
        checks,
        name="twin_validation_checksum_manifest",
        category="observatory",
        passed=len(entries) > 0,
        expected="non-empty SHA-256 checksum manifest",
        observed=f"{len(entries)} entries",
    )


def write_reports(
    checks: list[AuditCheck],
    started_at: datetime,
    elapsed_seconds: float,
) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    passed_count = sum(check.passed for check in checks)
    failed_count = len(checks) - passed_count
    accepted = failed_count == 0

    report = {
        "project": "PrimeNet",
        "audit": "Architecture Acceptance Audit",
        "version": VERSION,
        "status": "ACCEPTED" if accepted else "REJECTED",
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime_seconds": elapsed_seconds,
        "primenet_root": str(PRIMENET_ROOT),
        "repository_root": str(REPOSITORY_ROOT),
        "checks_total": len(checks),
        "checks_passed": passed_count,
        "checks_failed": failed_count,
        "checks": [asdict(check) for check in checks],
    }

    JSON_REPORT.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    lines: list[str] = [
        "=" * 80,
        f"PrimeNet Architecture Acceptance Audit v{VERSION}",
        "=" * 80,
        f"PrimeNet root   : {PRIMENET_ROOT}",
        f"Repository root : {REPOSITORY_ROOT}",
        f"Status          : {report['status']}",
        f"Checks passed   : {passed_count}",
        f"Checks failed   : {failed_count}",
        f"Runtime         : {elapsed_seconds:.3f} sec",
        "=" * 80,
        "",
    ]

    categories = sorted({check.category for check in checks})

    for category in categories:
        lines.append(category.upper())
        lines.append("-" * 80)

        for check in [item for item in checks if item.category == category]:
            status = "PASS" if check.passed else "FAIL"
            lines.append(f"[{status}] {check.name}")
            lines.append(f"  Expected : {check.expected}")
            lines.append(f"  Observed : {check.observed}")

            if check.details:
                for detail_line in check.details.splitlines():
                    lines.append(f"  Detail   : {detail_line}")

        lines.append("")

    lines.append("=" * 80)
    lines.append("[ACCEPTED]" if accepted else "[REJECTED]")
    lines.append(
        "PrimeNet satisfies the current architecture contract."
        if accepted
        else "PrimeNet does not yet satisfy the architecture contract."
    )
    lines.append("=" * 80)

    TEXT_REPORT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def print_console_summary(
    checks: list[AuditCheck],
    elapsed_seconds: float,
) -> int:
    passed_count = sum(check.passed for check in checks)
    failed_checks = [check for check in checks if not check.passed]

    print()
    print("=" * 80)
    print("PrimeNet Architecture Acceptance Audit Summary")
    print("=" * 80)
    print(f"Checks total  : {len(checks):,}")
    print(f"Checks passed : {passed_count:,}")
    print(f"Checks failed : {len(failed_checks):,}")
    print(f"Runtime       : {elapsed_seconds:.3f} sec")
    print(f"JSON report   : {JSON_REPORT}")
    print(f"Text report   : {TEXT_REPORT}")
    print("=" * 80)

    if failed_checks:
        print()
        print("Failed checks:")
        for check in failed_checks:
            print(f"  [FAIL] {check.category}: {check.name}")
            print(f"         expected={check.expected}")
            print(f"         observed={check.observed}")

        print()
        print("=" * 80)
        print("[REJECTED]")
        print("PrimeNet does not yet satisfy the architecture contract.")
        print("=" * 80)
        return 1

    print()
    print("=" * 80)
    print("[ACCEPTED]")
    print("PrimeNet satisfies the current architecture contract.")
    print("=" * 80)
    return 0


def main() -> int:
    started_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()

    print("=" * 80)
    print(f"PrimeNet Architecture Acceptance Audit v{VERSION}")
    print("=" * 80)
    print(f"PrimeNet root   : {PRIMENET_ROOT}")
    print(f"Repository root : {REPOSITORY_ROOT}")
    print("Mode            : read-only")
    print("=" * 80)

    checks: list[AuditCheck] = []

    print("[1/13] Checking required directories...")
    check_required_directories(checks)

    print("[2/13] Checking required files...")
    check_required_files(checks)

    print("[3/13] Checking superseded active modules...")
    check_superseded_active_modules(checks)

    print("[4/13] Parsing and compiling active Python source in memory...")
    check_python_syntax(checks)

    print("[5/13] Checking malformed imports...")
    check_malformed_imports(checks)

    print("[6/13] Checking Platform import namespace...")
    check_platform_namespace_imports(checks)

    print("[7/13] Checking generated cache artifacts...")
    check_generated_cache_artifacts(checks)

    print("[8/13] Checking .gitignore rules...")
    check_gitignore(checks)

    print("[9/13] Importing canonical modules...")
    check_canonical_imports(checks)

    print("[10/13] Checking obsolete active references...")
    check_obsolete_text_references(checks)

    print("[11/13] Checking numeric repository order...")
    check_numeric_repository_order(checks)

    print("[12/13] Checking repository acceptance provenance...")
    check_repository_acceptance_summary(checks)

    print("[13/13] Checking Twin Prime Observatory provenance...")
    check_twin_census_summary(checks)
    check_validation_package_checksums(checks)

    elapsed_seconds = time.perf_counter() - t0

    write_reports(checks, started_at, elapsed_seconds)
    return print_console_summary(checks, elapsed_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
