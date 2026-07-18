# PrimeNet Publisher optional-observatory hardening patch v2
# Run from C:\PrimeNet:
#   powershell -ExecutionPolicy Bypass -File .\maintenance\patch_optional_observatories_v2.ps1

$ErrorActionPreference = "Stop"

$PrimeNetRoot = "C:\PrimeNet"
$PublicationRoot = Join-Path $PrimeNetRoot "publication"
$TablesPath = Join-Path $PublicationRoot "publisher\tables.py"
$AdapterPath = Join-Path $PublicationRoot "publisher\repository_adapter.py"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

Write-Host ""
Write-Host ("=" * 78)
Write-Host "PrimeNet Publisher: Optional Observatory Hardening v2"
Write-Host ("=" * 78)

foreach ($Path in @($TablesPath, $AdapterPath)) {
    if (-not (Test-Path $Path)) {
        throw "Required file not found: $Path"
    }

    $Backup = "$Path.$Timestamp.bak"
    Copy-Item $Path $Backup -Force
    Write-Host "[BACKUP] $Backup"
}

$PatchCode = @'
from pathlib import Path
import re

tables_path = Path(r"C:\PrimeNet\publication\publisher\tables.py")
original = tables_path.read_text(encoding="utf-8-sig")
text = original

lookup_pattern = re.compile(
    r"stats\[\s*(['\"])(twin_[A-Za-z0-9_]+|steady_[A-Za-z0-9_]+)\1\s*\]"
)

text, replacement_count = lookup_pattern.subn(
    lambda match: f"stats.get({match.group(2)!r}, 'N/A')",
    text,
)

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

needle_variants = (
    "tables=make_tables(stats)",
    "tables = make_tables(stats)",
)

if "[SKIP] table07_observational_performance" not in text:
    needle = next((item for item in needle_variants if item in text), None)

    if needle is None:
        raise RuntimeError(
            "Could not locate make_tables(stats) in tables.py. "
            "No changes were written."
        )

    replacement = (
        needle
        + "\n"
        + " if not has_twin_performance(stats):\n"
        + "  removed=tables.pop('table07_observational_performance',None)\n"
        + "  if removed is not None:\n"
        + "   print('  [SKIP] table07_observational_performance "
          "(accepted twin-prime performance analysis unavailable)')"
    )

    text = text.replace(needle, replacement, 1)

compile(text, str(tables_path), "exec")

tables_path.write_text(
    text.rstrip() + "\n",
    encoding="utf-8",
    newline="\n",
)

print(f"[PATCHED] {tables_path}")
print(f"[OPTIONAL LOOKUPS CONVERTED] {replacement_count}")
print("[SOURCE COMPILE] PASSED")
'@

$PatchCode | py -B -
if ($LASTEXITCODE -ne 0) {
    throw "Python patch failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "Compile and import checks"
Write-Host ("-" * 78)

py -B -m py_compile `
    "$PublicationRoot\publisher\tables.py" `
    "$PublicationRoot\publisher\repository_adapter.py"

if ($LASTEXITCODE -ne 0) {
    throw "Compile check failed with exit code $LASTEXITCODE."
}

Push-Location $PublicationRoot
try {
    py -B -c "import publisher.tables; import publisher.repository_adapter; print('[PASSED] IMPORT SAFE')"
    if ($LASTEXITCODE -ne 0) {
        throw "Import check failed with exit code $LASTEXITCODE."
    }

    py -B -c "from pathlib import Path; import yaml; from publisher.repository_adapter import load_repository_stats; from publisher.tables import build_all,has_twin_performance; root=Path.cwd(); config=yaml.safe_load((root/'publication.yaml').read_text(encoding='utf-8')); stats=load_repository_stats(root,config); print('TWIN PERFORMANCE AVAILABLE =',has_twin_performance(stats)); tables=build_all(root/config['paths']['tables'],stats); print('GENERATED TABLES =',list(tables));"
    if ($LASTEXITCODE -ne 0) {
        throw "Table-generation test failed with exit code $LASTEXITCODE."
    }
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
Write-Host ("=" * 78)
Write-Host "[PASSED] Optional observatory hardening completed"
Write-Host ("=" * 78)
Write-Host ""
Write-Host "Next command:"
Write-Host "  cd C:\PrimeNet"
Write-Host "  .\maintenance\build_publication.ps1"