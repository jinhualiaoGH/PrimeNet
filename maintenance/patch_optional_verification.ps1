# PrimeNet Publisher optional-verification hardening patch
# Run from C:\PrimeNet:
#   powershell -ExecutionPolicy Bypass -File .\maintenance\patch_optional_verification.ps1

$ErrorActionPreference = "Stop"

$PrimeNetRoot = "C:\PrimeNet"
$PublicationRoot = Join-Path $PrimeNetRoot "publication"
$ReviewPath = Join-Path $PublicationRoot "publisher\review.py"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

Write-Host ""
Write-Host ("=" * 78)
Write-Host "PrimeNet Publisher: Optional Verification Hardening"
Write-Host ("=" * 78)

if (-not (Test-Path $ReviewPath)) {
    throw "Required file not found: $ReviewPath"
}

$Backup = "$ReviewPath.$Timestamp.bak"
Copy-Item $ReviewPath $Backup -Force
Write-Host "[BACKUP] $Backup"

$PatchCode = @'
from pathlib import Path

path = Path(r"C:\PrimeNet\publication\publisher\review.py")
text = path.read_text(encoding="utf-8-sig")

marker = "OPTIONAL_PUBLICATION_TABLES"
if marker in text:
    print("[ALREADY PATCHED]", path)
else:
    helper = (
        "\nOPTIONAL_PUBLICATION_TABLES = {\n"
        "    'table07_observational_performance',\n"
        "}\n\n"
        "def _active_review_tables(table_dir, tables):\n"
        "    active = []\n"
        "    for table_name in tables:\n"
        "        paths = [\n"
        "            table_dir / f'{table_name}.{ext}'\n"
        "            for ext in ('csv', 'md', 'docx')\n"
        "        ]\n"
        "        if (\n"
        "            table_name in OPTIONAL_PUBLICATION_TABLES\n"
        "            and not any(path.exists() for path in paths)\n"
        "        ):\n"
        "            print(\n"
        "                f'[SKIP] Optional verification table unavailable: '\n"
        "                f'{table_name}'\n"
        "            )\n"
        "            continue\n"
        "        active.append(table_name)\n"
        "    return active\n\n"
    )

    first_def = text.find("def ")
    if first_def < 0:
        raise RuntimeError("Could not locate first function in review.py.")

    text = text[:first_def] + helper + text[first_def:]

    old_variants = (
        "for t in tables:",
        "for table in tables:",
    )

    matched = next((item for item in old_variants if item in text), None)
    if matched is None:
        raise RuntimeError(
            "Could not locate the table verification loop in review.py. "
            "No changes were written."
        )

    variable = "t" if matched == "for t in tables:" else "table"
    replacement = (
        f"for {variable} in _active_review_tables(table_dir, tables):"
    )
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

py -B -m py_compile "$ReviewPath"
if ($LASTEXITCODE -ne 0) {
    throw "Compile check failed with exit code $LASTEXITCODE."
}

Push-Location $PublicationRoot
try {
    py -B -c "import publisher.review; print('[PASSED] IMPORT SAFE')"
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
Write-Host "[PASSED] Optional verification hardening completed"
Write-Host ("=" * 78)
Write-Host ""
Write-Host "Next command:"
Write-Host "  cd C:\PrimeNet"
Write-Host "  .\maintenance\build_publication.ps1"