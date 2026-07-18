param(
    [string]$PrimeNetRoot = "C:\PrimeNet"
)

$ErrorActionPreference = "Stop"
$Here = $PSScriptRoot

Write-Host ""
Write-Host "PrimeNet v1.0 Release-Aware Cleanup"
Write-Host ("=" * 80)

Write-Host ""
Write-Host "1. PREPARE RELEASE AREA"
& "$Here\01_prepare_release_area.ps1" -PrimeNetRoot $PrimeNetRoot -Apply

Write-Host ""
Write-Host "2. ARCHIVE DEVELOPMENT ARTIFACTS"
& "$Here\02_archive_release_artifacts.ps1" -PrimeNetRoot $PrimeNetRoot -Apply

Write-Host ""
Write-Host "3. CLEAN DISPOSABLE CACHES"
& "$PrimeNetRoot\maintenance\03_clean_disposable_caches.ps1" -PrimeNetRoot $PrimeNetRoot -Apply

Write-Host ""
Write-Host "4. UPDATE .GITIGNORE"
& "$PrimeNetRoot\maintenance\05_update_gitignore.ps1" -PrimeNetRoot $PrimeNetRoot -Apply

Write-Host ""
Write-Host "5. VERIFY CLEANUP"
& "$PrimeNetRoot\maintenance\06_verify_cleanup.ps1" -PrimeNetRoot $PrimeNetRoot

Write-Host ""
Write-Host "[COMPLETE] Release-aware cleanup completed."
Write-Host "[NEXT] Review C:\PrimeNet\release\v1.0 and run git status."
