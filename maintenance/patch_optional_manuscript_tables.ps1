# PrimeNet Publisher manuscript optional-table hardening patch
# Run from C:\PrimeNet:
#   powershell -ExecutionPolicy Bypass -File .\maintenance\patch_optional_manuscript_tables.ps1

$ErrorActionPreference = "Stop"

$PrimeNetRoot = "C:\PrimeNet"
$PublicationRoot = Join-Path $PrimeNetRoot "publication"
$ManuscriptPath = Join-Path $PublicationRoot "publisher\manuscript.py"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

Write-Host ""
Write-Host ("=" * 78)
Write-Host "PrimeNet Publisher: Optional Manuscript Table Hardening"
Write-Host ("=" * 78)

if (-not (Test-Path $ManuscriptPath)) {
    throw "Required file not found: $ManuscriptPath"
}

$Backup = "$ManuscriptPath.$Timestamp.bak"
Copy-Item $ManuscriptPath $Backup -Force
Write-Host "[BACKUP] $Backup"

$PatchCode = @'
from pathlib import Path

path = Path(r"C:\PrimeNet\publication\publisher\manuscript.py")
text = path.read_text(encoding="utf-8-sig")

old_variants = (
    "_add_table(doc,tables[sec['table']],table_font)",
    '_add_table(doc,tables[sec["table"]],table_font)',
)

replacement = (
    "table_name=sec['table']; "
    "table_rows=tables.get(table_name); "
    "print(f'  [SKIP] manuscript table {table_name} (unavailable)') "
    "if table_rows is None else _add_table(doc,table_rows,table_font)"
)

matched = None
for old in old_variants:
    if old in text:
        matched = old
        break

if matched is None:
    if "[SKIP] manuscript table" in text:
        print("[ALREADY PATCHED]", path)
    else:
        raise RuntimeError(
            "Expected manuscript table insertion call was not found. "
            "No changes were written."
        )
else:
    text = text.replace(matched, replacement, 1)
    compile(text, str(path), "exec")
    path.write_text(
        text.rstrip() + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("[PATCHED]", path)
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
    "$PublicationRoot\publisher\manuscript.py"

if ($LASTEXITCODE -ne 0) {
    throw "Compile check failed with exit code $LASTEXITCODE."
}

Push-Location $PublicationRoot
try {
    py -B -c "import publisher.manuscript; print('[PASSED] IMPORT SAFE')"
    if ($LASTEXITCODE -ne 0) {
        throw "Import check failed with exit code $LASTEXITCODE."
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
Write-Host "[PASSED] Optional manuscript-table hardening completed"
Write-Host ("=" * 78)
Write-Host ""
Write-Host "Next command:"
Write-Host "  cd C:\PrimeNet"
Write-Host "  .\maintenance\build_publication.ps1"