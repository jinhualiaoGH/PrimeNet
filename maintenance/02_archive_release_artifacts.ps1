param(
    [string]$PrimeNetRoot = "C:\PrimeNet",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

$Reports = Join-Path $PrimeNetRoot "maintenance\reports"
$ArchiveRoot = Join-Path $PrimeNetRoot "archive"
$DevelopmentArchive = Join-Path $ArchiveRoot "development_packages"
$SnapshotArchive = Join-Path $ArchiveRoot "historical_snapshots"
$BackupArchive = Join-Path $ArchiveRoot "installation_backups"

New-Item -ItemType Directory -Path $Reports -Force | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Manifest = Join-Path $Reports "archive_moves_release_aware_$Timestamp.csv"
$Log = Join-Path $Reports "archive_moves_release_aware_$Timestamp.txt"

$DevelopmentPatterns = @(
    "PrimeNet_Publisher_*",
    "PrimeNet_publisher_*",
    "PrimeNet_theory_validation_figures_*",
    "PrimeNet_evidence_figures_*",
    "figure_evidence_bundle*",
    "*_inspection*",
    "*_patch*"
)

$SnapshotPatterns = @(
    "publication_before_*",
    "publisher_before_*"
)

$ProtectedNames = @(
    "Platform","publication","paper","catalog","docs","config","core",
    "instruments","observatories","scripts","tests","products",
    "maintenance","archive","release","Lab","logs","reports","runs","tmp","cache"
)

$ReleaseArtifactNames = @(
    "PrimeNet_Publisher_v2_4_3_Figure1_Final_Real.zip"
)

$candidates = @()

foreach ($item in Get-ChildItem -LiteralPath $PrimeNetRoot -Force) {
    if ($ProtectedNames -contains $item.Name) { continue }
    if ($ReleaseArtifactNames -contains $item.Name) { continue }

    $category = $null
    $destinationRoot = $null

    if ($item.Name -eq "backup") {
        $category = "INSTALLATION_BACKUP"
        $destinationRoot = $BackupArchive
    }

    if (-not $category) {
        foreach ($pattern in $SnapshotPatterns) {
            if ($item.Name -like $pattern) {
                $category = "HISTORICAL_SNAPSHOT"
                $destinationRoot = $SnapshotArchive
                break
            }
        }
    }

    if (-not $category) {
        foreach ($pattern in $DevelopmentPatterns) {
            if ($item.Name -like $pattern) {
                $category = "DEVELOPMENT_PACKAGE"
                $destinationRoot = $DevelopmentArchive
                break
            }
        }
    }

    if ($category) {
        $candidates += [pscustomobject]@{
            Source = $item.FullName
            Destination = Join-Path $destinationRoot $item.Name
            Category = $category
            Status = if ($Apply) { "PENDING" } else { "DRY-RUN" }
        }
    }
}

$candidates = $candidates | Sort-Object Source -Unique

if (-not $Apply) {
    $candidates | Export-Csv -LiteralPath $Manifest -NoTypeInformation -Encoding UTF8
    @(
        "PrimeNet v1.0 Release-Aware Archive Plan"
        ("=" * 80)
        "Mode : DRY-RUN"
        ""
        ($candidates | ForEach-Object {
            "[PLAN][$($_.Category)] $($_.Source) -> $($_.Destination)"
        })
        ""
        "Protected release artifact:"
        "  C:\PrimeNet\PrimeNet_Publisher_v2_4_3_Figure1_Final_Real.zip"
        ""
        "Nothing was moved. Rerun with -Apply after review."
    ) | Set-Content -LiteralPath $Log -Encoding UTF8

    Write-Host "[DRY-RUN] $($candidates.Count) archive candidate(s)"
    Write-Host "[PROTECTED] PrimeNet_Publisher_v2_4_3_Figure1_Final_Real.zip"
    Write-Host "[MANIFEST] $Manifest"
    exit 0
}

foreach ($dir in @($DevelopmentArchive,$SnapshotArchive,$BackupArchive)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

foreach ($row in $candidates) {
    $destination = $row.Destination
    if (Test-Path -LiteralPath $destination) {
        $destination = "$destination`_$(Get-Date -Format yyyyMMdd_HHmmss)"
        $row.Destination = $destination
    }
    Move-Item -LiteralPath $row.Source -Destination $destination
    $row.Status = "MOVED"
    Write-Host "[MOVED][$($row.Category)] $($row.Source)"
}

$candidates | Export-Csv -LiteralPath $Manifest -NoTypeInformation -Encoding UTF8

Write-Host ""
Write-Host "[COMPLETE] Archived $($candidates.Count) item(s)."
Write-Host "[MANIFEST] $Manifest"
