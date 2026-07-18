# PrimeNet Publisher optional-observatory hardening patch
# Run from C:\PrimeNet:
#   powershell -ExecutionPolicy Bypass -File .\maintenance\patch_optional_observatories.ps1

$ErrorActionPreference = "Stop"

$PrimeNetRoot = "C:\PrimeNet"
$PublicationRoot = Join-Path $PrimeNetRoot "publication"
$TablesPath = Join-Path $PublicationRoot "publisher\tables.py"
$AdapterPath = Join-Path $PublicationRoot "publisher\repository_adapter.py"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

Write-Host ""
Write-Host ("=" * 78)
Write-Host "PrimeNet Publisher: Optional Observatory Hardening"
Write-Host ("=" * 78)

foreach ($Path in @($TablesPath, $AdapterPath)) {
    if (-not (Test-Path $Path)) {
        throw "Required file not found: $Path"
    }
    Copy-Item $Path "$Path.$Timestamp.bak" -Force
    Write-Host "[BACKUP] $Path.$Timestamp.bak"
}

@'
from pathlib import Path
import re

tables_path = Path(r"C:\PrimeNet\publication\publisher\tables.py")
text = tables_path.read_text(encoding="utf-8-sig")

pattern = re.compile(
    r"stats\[\s*(['\"])(twin_[A-Za-z0-9_]+|steady_[A-Za-z0-9_]+)\1\s*\]"
)

def replace_lookup(match):
    key = match.group(2)
    return f"stats.get({key!r}, 'N/A')"

text, replacement_count = pattern.subn(replace_lookup, text)

helper_lines = [
    "OPTIONAL_TWIN_PERFORMANCE_KEYS = (",
    '    "twin_numeric_domain",',
    '    "twin_partitions",',
    '    "twin_total_gaps",',
    '    "twin_total_events",',
    '    "twin_global_density",',
    '    "twin_end_to_end_runtime_min",',
    '    "twin_runtime_accounted_percent",',
    '    "steady_partitions",',
    '    "steady_total_gaps",',
    '    "steady_mean_runtime_sec",',
    '    "steady_median_runtime_sec",',
    '    "steady_runtime_cv_percent",',
    '    "steady_p95_runtime_sec",',
    '    "steady_gaps_per_sec",',
    ")",
    "",
    "",
    "def has_twin_performance(stats):",
    "    return all(",
    '        stats.get(key) not in (None, "", "N/A")',
    "        for key in OPTIONAL_TWIN_PERFORMANCE_KEYS",
    "    )",
    "",
    "",
]
helper = "\n".join(helper_lines)

if "def has_twin_performance(stats):" not in text:
    first_def = re.search(r"(?m)^def\s+", text)
    if not first_def:
        raise RuntimeError("Could not locate the first function in tables.py.")
    text = text[:first_def.start()] + helper + text[first_def.start():]

if "[SKIP] table07_observational_performance" not in text:
    match = re.search(
        r"(?m)^(?P<indent>\s*)tables\s*=\s*make_tables\(stats\)\s*$",
        text,
    )
    if not match:
        raise RuntimeError(
            "Could not locate the make_tables(stats) call in tables.py. "
            "No partial write was performed."
        )

    indent = match.group("indent")
    guard_lines = [
        "",
        f"{indent}if not has_twin_performance(stats):",
        f"{indent}    removed = tables.pop(",
        f'{indent}        "table07_observational_performance",',
        f"{indent}        None,",
        f"{indent}    )",
        f"{indent}    if removed is not None:",
        f"{indent}        print(",
        f'{indent}            "  [SKIP] table07_observational_performance "',
        f'{indent}            "(accepted twin-prime performance analysis unavailable)"',
        f"{indent}        )",
    ]
    insert_at = match.end()
    text = text[:insert_at] + "\n".join(guard_lines) + text[insert_at:]

tables_path.write_text(
    text.rstrip() + "\n",
    encoding="utf-8",
    newline="\n",
)

print(f"[PATCHED] {tables_path}")
print(f"[LOOKUPS MADE OPTIONAL] {replacement_count}")
'@ | py -B -

Write-Host ""
Write-Host "Compile and import checks"
Write-Host ("-" * 78)

py -B -m py_compile `
    "$PublicationRoot\publisher\tables.py" `
    "$PublicationRoot\publisher\repository_adapter.py"

Push-Location $PublicationRoot
try {
    py -B -c "import publisher.tables; import publisher.repository_adapter; print('[PASSED] IMPORT SAFE')"

    py -B -c "from pathlib import Path; import yaml; from publisher.repository_adapter import load_repository_stats; from publisher.tables import make_tables,has_twin_performance; root=Path.cwd(); config=yaml.safe_load((root/'publication.yaml').read_text(encoding='utf-8')); stats=load_repository_stats(root,config); tables=make_tables(stats); print('TWIN PERFORMANCE AVAILABLE =',has_twin_performance(stats)); print('TABLES BEFORE OPTIONAL FILTER =',list(tables));"
}
finally {
    Pop-Location
}

Remove-Item `
    "$PublicationRoot\publisher\__pycache__" `
    -Recurse `
    -Force `
    -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "[READY] Run:"
Write-Host "  cd C:\PrimeNet"
Write-Host "  .\maintenance\build_publication.ps1"