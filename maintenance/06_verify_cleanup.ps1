param(
    [string]$PrimeNetRoot = "C:\PrimeNet"
)

$ErrorActionPreference = "Stop"

$RequiredDirectories = @(
    "Platform",
    "publication",
    "paper",
    "catalog",
    "config",
    "core",
    "instruments",
    "observatories",
    "scripts",
    "tests",
    "maintenance"
)

$RequiredFiles = @(
    "README.md",
    "ARCHITECTURE.md",
    "CHANGELOG.md",
    "VERSION"
)

$failures = 0

Write-Host ""
Write-Host "PrimeNet v1.0 Post-Cleanup Verification"
Write-Host ("=" * 80)

foreach ($name in $RequiredDirectories) {
    $path = Join-Path $PrimeNetRoot $name
    if (Test-Path -LiteralPath $path -PathType Container) {
        Write-Host "[PASSED] Directory: $path"
    } else {
        Write-Host "[FAILED] Directory missing: $path"
        $failures++
    }
}

foreach ($name in $RequiredFiles) {
    $path = Join-Path $PrimeNetRoot $name
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        Write-Host "[PASSED] File: $path"
    } else {
        Write-Host "[FAILED] File missing: $path"
        $failures++
    }
}

$ReleaseComponents = @(
    (Join-Path $PrimeNetRoot "publication\build_publication.py"),
    (Join-Path $PrimeNetRoot "publication\verify_publication.py"),
    (Join-Path $PrimeNetRoot "Platform\tools\release_auditor.py")
)

foreach ($path in $ReleaseComponents) {
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        Write-Host "[PASSED] Release component: $path"
    } else {
        Write-Host "[FAILED] Release component missing: $path"
        $failures++
    }
}

Write-Host ""
if ($failures -eq 0) {
    Write-Host "Overall Status: PASSED"
    exit 0
}

Write-Host "Overall Status: FAILED ($failures required item(s) missing)"
exit 1
