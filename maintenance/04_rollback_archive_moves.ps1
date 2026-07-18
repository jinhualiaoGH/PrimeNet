param(
    [Parameter(Mandatory=$true)]
    [string]$ManifestPath,
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw "Manifest not found: $ManifestPath"
}

$rows = Import-Csv -LiteralPath $ManifestPath |
    Where-Object { $_.Status -eq "MOVED" } |
    Sort-Object Source -Descending

if (-not $Apply) {
    Write-Host "[DRY-RUN] Archive rollback plan"
    foreach ($row in $rows) {
        Write-Host "[PLAN] $($row.Destination) -> $($row.Source)"
    }
    Write-Host "Nothing was moved. Rerun with -Apply."
    exit 0
}

foreach ($row in $rows) {
    if (-not (Test-Path -LiteralPath $row.Destination)) {
        Write-Warning "Archived item missing: $($row.Destination)"
        continue
    }

    if (Test-Path -LiteralPath $row.Source) {
        throw "Cannot restore because the original source path already exists: $($row.Source)"
    }

    Move-Item -LiteralPath $row.Destination -Destination $row.Source
    Write-Host "[RESTORED] $($row.Source)"
}

Write-Host "[COMPLETE] Archive rollback finished."
