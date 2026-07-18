param(
    [string]$PrimeNetRoot = "C:\PrimeNet"
)

$ErrorActionPreference = "Stop"
$Here = $PSScriptRoot

Write-Host ""
Write-Host "PrimeNet v1.0 Maintenance Cleanup Workflow"
Write-Host ("=" * 72)
Write-Host "This workflow runs in DRY-RUN mode only."
Write-Host ""

& "$Here\01_inventory_cleanup.ps1" -PrimeNetRoot $PrimeNetRoot
& "$Here\02_archive_development_packages.ps1" -PrimeNetRoot $PrimeNetRoot
& "$Here\03_clean_disposable_caches.ps1" -PrimeNetRoot $PrimeNetRoot
& "$Here\05_update_gitignore.ps1" -PrimeNetRoot $PrimeNetRoot
& "$Here\06_verify_cleanup.ps1" -PrimeNetRoot $PrimeNetRoot

Write-Host ""
Write-Host "[COMPLETE] Dry-run workflow finished."
Write-Host "Review maintenance\reports before applying any changes."
