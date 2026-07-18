param(
    [string]$PrimeNetRoot = "C:\PrimeNet",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $PrimeNetRoot)) {
    throw "PrimeNet root not found: $PrimeNetRoot"
}

$Reports = Join-Path $PrimeNetRoot "maintenance\reports"
New-Item -ItemType Directory -Path $Reports -Force | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Log = Join-Path $Reports "disposable_cleanup_final_$Timestamp.txt"

$targets = @()

$targets += Get-ChildItem -LiteralPath $PrimeNetRoot -Directory -Recurse -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq "__pycache__" }

$targets += Get-ChildItem -LiteralPath $PrimeNetRoot -File -Recurse -Force -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Extension -eq ".pyc" -or
        $_.Name -eq "Thumbs.db" -or
        $_.Name -eq "Desktop.ini"
    }

$targets = $targets | Sort-Object FullName -Unique

if (-not $Apply) {
    @(
        "PrimeNet v1.0 Disposable Cache Cleanup"
        ("=" * 80)
        "Mode  : DRY-RUN"
        "Count : $($targets.Count)"
        ""
        ($targets | ForEach-Object { "[PLAN] $($_.FullName)" })
        ""
        "Nothing was deleted. Rerun with -Apply only after review."
    ) | Set-Content -LiteralPath $Log -Encoding UTF8

    Write-Host "[DRY-RUN] $($targets.Count) disposable item(s)"
    Write-Host "[CREATED] $Log"
    exit 0
}

foreach ($target in $targets) {
    if (Test-Path -LiteralPath $target.FullName) {
        Remove-Item -LiteralPath $target.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host "[REMOVED] $($target.FullName)"
}

@(
    "PrimeNet v1.0 Disposable Cache Cleanup"
    ("=" * 80)
    "Mode    : APPLY"
    "Removed : $($targets.Count)"
    ""
    ($targets | ForEach-Object { "[REMOVED] $($_.FullName)" })
) | Set-Content -LiteralPath $Log -Encoding UTF8

Write-Host "[COMPLETE] Removed $($targets.Count) disposable item(s)."
Write-Host "[LOG] $Log"
