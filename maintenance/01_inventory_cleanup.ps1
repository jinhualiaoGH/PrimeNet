param(
    [string]$PrimeNetRoot = "C:\PrimeNet"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $PrimeNetRoot)) {
    throw "PrimeNet root not found: $PrimeNetRoot"
}

$Maintenance = Join-Path $PrimeNetRoot "maintenance"
$Reports = Join-Path $Maintenance "reports"
New-Item -ItemType Directory -Path $Reports -Force | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Csv = Join-Path $Reports "cleanup_inventory_final_$Timestamp.csv"
$Txt = Join-Path $Reports "cleanup_inventory_final_$Timestamp.txt"

$KeepDirectories = @(
    ".git",
    "Platform",
    "publication",
    "paper",
    "catalog",
    "docs",
    "config",
    "core",
    "instruments",
    "observatories",
    "scripts",
    "tests",
    "products",
    "maintenance",
    "archive"
)

$KeepFiles = @(
    ".gitignore",
    "README.md",
    "ARCHITECTURE.md",
    "CHANGELOG.md",
    "CITATION.cff",
    "LICENSE",
    "VERSION",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "manifest.json",
    "PrimeNet_Principles.md"
)

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

$ReviewNames = @(
    "Lab",
    "logs",
    "reports",
    "runs",
    "tmp",
    "cache"
)

function Get-Classification {
    param([System.IO.FileSystemInfo]$Item)

    if ($Item.PSIsContainer -and $KeepDirectories -contains $Item.Name) {
        return "KEEP"
    }

    if (-not $Item.PSIsContainer -and $KeepFiles -contains $Item.Name) {
        return "KEEP"
    }

    if ($ReviewNames -contains $Item.Name) {
        return "REVIEW_RUNTIME"
    }

    if ($Item.Name -eq "backup") {
        return "ARCHIVE_BACKUP"
    }

    foreach ($pattern in $SnapshotPatterns) {
        if ($Item.Name -like $pattern) {
            return "ARCHIVE_SNAPSHOT"
        }
    }

    foreach ($pattern in $DevelopmentPatterns) {
        if ($Item.Name -like $pattern) {
            return "ARCHIVE_DEVELOPMENT"
        }
    }

    if ($Item.Name -eq "__pycache__" -or
        $Item.Extension -eq ".pyc" -or
        $Item.Name -eq "Thumbs.db" -or
        $Item.Name -eq "Desktop.ini") {
        return "DISPOSABLE"
    }

    if ($Item.Name -eq "Fig. 14.png") {
        return "REVIEW_LOOSE_FILE"
    }

    if ($Item.Name -like "*.zip") {
        return "REVIEW_ARCHIVE_FILE"
    }

    return "REVIEW_OTHER"
}

$rows = foreach ($item in Get-ChildItem -LiteralPath $PrimeNetRoot -Force | Sort-Object Name) {
    [pscustomobject]@{
        Name           = $item.Name
        FullPath       = $item.FullName
        Type           = if ($item.PSIsContainer) { "Directory" } else { "File" }
        Classification = Get-Classification $item
        SizeBytes      = if ($item.PSIsContainer) { "" } else { $item.Length }
        LastWriteTime  = $item.LastWriteTime
    }
}

$rows | Export-Csv -LiteralPath $Csv -NoTypeInformation -Encoding UTF8

$summary = $rows |
    Group-Object Classification |
    Sort-Object Name |
    ForEach-Object { "{0,-22} {1,5}" -f $_.Name, $_.Count }

@(
    "PrimeNet v1.0 Final Cleanup Inventory"
    ("=" * 80)
    "Root      : $PrimeNetRoot"
    "Generated : $(Get-Date -Format o)"
    ""
    "Classification Summary"
    ("-" * 80)
    $summary
    ""
    "KEEP"
    ("-" * 80)
    ($rows | Where-Object Classification -eq "KEEP" | ForEach-Object { $_.FullPath })
    ""
    "ARCHIVE"
    ("-" * 80)
    ($rows | Where-Object Classification -like "ARCHIVE_*" | ForEach-Object {
        "[$($_.Classification)] $($_.FullPath)"
    })
    ""
    "REVIEW"
    ("-" * 80)
    ($rows | Where-Object Classification -like "REVIEW_*" | ForEach-Object {
        "[$($_.Classification)] $($_.FullPath)"
    })
    ""
    "No files were moved or deleted."
) | Set-Content -LiteralPath $Txt -Encoding UTF8

Write-Host ""
Write-Host "PrimeNet v1.0 Final Cleanup Inventory"
Write-Host ("=" * 80)
$summary | ForEach-Object { Write-Host $_ }
Write-Host ""
Write-Host "[CREATED] $Csv"
Write-Host "[CREATED] $Txt"
Write-Host "[SAFE] No files were moved or deleted."
