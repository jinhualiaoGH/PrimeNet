param(
    [string]$PrimeNetRoot = "C:\PrimeNet",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $PrimeNetRoot)) {
    throw "PrimeNet root not found: $PrimeNetRoot"
}

$Maintenance = Join-Path $PrimeNetRoot "maintenance"
$Reports = Join-Path $Maintenance "reports"
$ArchiveRoot = Join-Path $PrimeNetRoot "archive\development_packages"
New-Item -ItemType Directory -Path $Reports -Force | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Manifest = Join-Path $Reports "archive_moves_$Timestamp.csv"
$Log = Join-Path $Reports "archive_moves_$Timestamp.txt"

$Patterns = @(
    "PrimeNet_Publisher_*",
    "PrimeNet_publisher_*",
    "PrimeNet_theory_validation_figures_*",
    "PrimeNet_evidence_figures_*",
    "figure_evidence_bundle*",
    "*_inspection*",
    "*_patch*"
)

$Excluded = @(
    "PrimeNet_Publisher_v2_4_3_Figure1_Final_Real"
)

$candidates = @()
foreach ($pattern in $Patterns) {
    $candidates += Get-ChildItem -LiteralPath $PrimeNetRoot -Force |
        Where-Object { $_.Name -like $pattern }
}

$candidates = $candidates |
    Where-Object {
        $_.FullName -ne $ArchiveRoot -and
        $_.Name -notin $Excluded -and
        $_.Name -ne "maintenance" -and
        $_.Name -ne "archive"
    } |
    Sort-Object FullName -Unique

$rows = foreach ($item in $candidates) {
    $destination = Join-Path $ArchiveRoot $item.Name
    [pscustomobject]@{
        Source      = $item.FullName
        Destination = $destination
        Type        = if ($item.PSIsContainer) { "Directory" } else { "File" }
        Status      = if ($Apply) { "PENDING" } else { "DRY-RUN" }
    }
}

if (-not $Apply) {
    $rows | Export-Csv -LiteralPath $Manifest -NoTypeInformation -Encoding UTF8
    @(
        "PrimeNet Development Package Archive Plan"
        ("=" * 72)
        "Mode      : DRY-RUN"
        "Root      : $PrimeNetRoot"
        "Archive   : $ArchiveRoot"
        ""
        ($rows | ForEach-Object { "[PLAN] $($_.Source) -> $($_.Destination)" })
        ""
        "Nothing was moved. Rerun with -Apply after review."
    ) | Set-Content -LiteralPath $Log -Encoding UTF8

    Write-Host "[DRY-RUN] $($rows.Count) candidate(s)"
    $rows | Format-Table -AutoSize
    Write-Host "[CREATED] $Manifest"
    Write-Host "[CREATED] $Log"
    exit 0
}

New-Item -ItemType Directory -Path $ArchiveRoot -Force | Out-Null

foreach ($row in $rows) {
    if (Test-Path -LiteralPath $row.Destination) {
        $suffix = Get-Date -Format "yyyyMMdd_HHmmss"
        $row.Destination = "$($row.Destination)_$suffix"
    }

    Move-Item -LiteralPath $row.Source -Destination $row.Destination
    $row.Status = "MOVED"
    Write-Host "[MOVED] $($row.Source)"
}

$rows | Export-Csv -LiteralPath $Manifest -NoTypeInformation -Encoding UTF8
@(
    "PrimeNet Development Package Archive"
    ("=" * 72)
    "Mode      : APPLY"
    "Root      : $PrimeNetRoot"
    "Archive   : $ArchiveRoot"
    "Moved     : $($rows.Count)"
    ""
    ($rows | ForEach-Object { "[MOVED] $($_.Source) -> $($_.Destination)" })
    ""
    "Rollback manifest: $Manifest"
) | Set-Content -LiteralPath $Log -Encoding UTF8

Write-Host ""
Write-Host "[COMPLETE] Archived $($rows.Count) development package(s)."
Write-Host "[MANIFEST] $Manifest"
Write-Host "[ROLLBACK] Use 04_rollback_archive_moves.ps1 -ManifestPath `"$Manifest`" -Apply"
