# ============================================================
# PrimeNet v1.0 Finalization - Move Uncertain Files to Review
#
# Moves selected uncertain / superseded files from:
#   C:\PrimeNet
# to:
#   C:\PrimeNet_Review
#
# This does NOT delete files.
# It preserves relative folder structure.
# ============================================================

$PROJECT_ROOT = "C:\PrimeNet"
$REVIEW_ROOT  = "C:\PrimeNet_Review"

$items = @(
    "scripts\repository\clean_repository_duplicates.py",
    "scripts\repository\generate_prime_repository.py",
    "scripts\repository\README.md.txt",

    "scripts\repository\generate_prime_range.py",
    "scripts\repository\verify_prime_file.py",
    "scripts\repository\audit_prime_files.py",
    "scripts\repository\build_repository_index.py",
    "scripts\repository\compute_checksums.py",

    "scripts\information\entropy_observatory.py",
    "scripts\information\transition_observatory.py",
    "scripts\information\information_geometry_observatory.py",
    "scripts\information\invariant_observatory.py",
    "scripts\information\taxonomy_observatory.py"
)

Write-Host ""
Write-Host "============================================="
Write-Host " PrimeNet Move-to-Review Iteration 3"
Write-Host "============================================="
Write-Host "Project root = $PROJECT_ROOT"
Write-Host "Review root  = $REVIEW_ROOT"
Write-Host ""

if (!(Test-Path $PROJECT_ROOT)) {
    Write-Host "ERROR: Project root does not exist: $PROJECT_ROOT"
    exit 1
}

New-Item -ItemType Directory -Force -Path $REVIEW_ROOT | Out-Null

$logFile = Join-Path $REVIEW_ROOT "REVIEW_LOG.md"

if (!(Test-Path $logFile)) {
    @"
# PrimeNet v1.0 Review Log

Files moved here are under review, not deleted.

"@ | Set-Content $logFile -Encoding UTF8
}

Read-Host "Press ENTER to move selected files to PrimeNet_Review"

foreach ($relative in $items) {
    $source = Join-Path $PROJECT_ROOT $relative
    $target = Join-Path $REVIEW_ROOT $relative
    $targetDir = Split-Path $target -Parent

    if (Test-Path $source) {
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

        Write-Host "Moving: $relative"
        Move-Item -Path $source -Destination $target -Force

        Add-Content $logFile ""
        Add-Content $logFile "## Moved"
        Add-Content $logFile ""
        Add-Content $logFile "- Source: C:\PrimeNet\$relative"
        Add-Content $logFile "- Target: C:\PrimeNet_Review\$relative"
        Add-Content $logFile "- Reason: Under review for PrimeNet v1.0 finalization."
        Add-Content $logFile "- Decision: Pending"
    }
    else {
        Write-Host "Skipping missing: $relative"
    }
}

Write-Host ""
Write-Host "Removing newly empty folders under C:\PrimeNet\scripts..."

do {
    $deletedThisPass = 0

    Get-ChildItem "$PROJECT_ROOT\scripts" -Directory -Recurse -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending |
    ForEach-Object {
        if (@(Get-ChildItem $_.FullName -Force).Count -eq 0) {
            Write-Host "Removing empty folder: $($_.FullName)"
            Remove-Item $_.FullName -Force
            $deletedThisPass++
        }
    }
} while ($deletedThisPass -gt 0)

Write-Host ""
Write-Host "============================================="
Write-Host "Move-to-review complete."
Write-Host "Nothing was deleted permanently."
Write-Host "Review log: $logFile"
Write-Host "============================================="