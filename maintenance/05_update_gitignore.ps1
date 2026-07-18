param(
    [string]$PrimeNetRoot = "C:\PrimeNet",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$GitIgnore = Join-Path $PrimeNetRoot ".gitignore"

$Required = @(
    "# PrimeNet local and regenerable artifacts",
    "__pycache__/",
    "*.py[cod]",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    "Thumbs.db",
    "Desktop.ini",
    ".DS_Store",
    ".vscode/",
    "maintenance/reports/",
    "archive/development_packages/",
    "archive/installation_backups/",
    "backup/",
    "cache/",
    "tmp/",
    "*.tmp"
)

$current = if (Test-Path -LiteralPath $GitIgnore) {
    Get-Content -LiteralPath $GitIgnore
} else {
    @()
}

$missing = $Required | Where-Object { $_ -notin $current }

if (-not $Apply) {
    Write-Host "[DRY-RUN] Missing .gitignore entries:"
    $missing | ForEach-Object { Write-Host "  $_" }
    Write-Host "Nothing was changed. Rerun with -Apply."
    exit 0
}

if (-not (Test-Path -LiteralPath $GitIgnore)) {
    New-Item -ItemType File -Path $GitIgnore -Force | Out-Null
}

if ($missing.Count -gt 0) {
    Add-Content -LiteralPath $GitIgnore -Value @("", $missing) -Encoding UTF8
}

Write-Host "[UPDATED] $GitIgnore"
Write-Host "[ADDED] $($missing.Count) missing pattern(s)"
