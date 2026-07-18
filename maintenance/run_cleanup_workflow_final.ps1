param(
    [string]$PrimeNetRoot = "C:\PrimeNet"
)

$ErrorActionPreference = "Stop"
$Here = $PSScriptRoot

Write-Host ""
Write-Host "PrimeNet v1.0 Final Cleanup Workflow"
Write-Host ("=" * 80)
Write-Host "This workflow is DRY-RUN only."
Write-Host ""

& "$Here\01_inventory_cleanup.ps1" -PrimeNetRoot $PrimeNetRoot
& "$Here\02_archive_release_artifacts.ps1" -PrimeNetRoot $PrimeNetRoot
& "$Here\03_clean_disposable_caches.ps1" -PrimeNetRoot $PrimeNetRoot
& "$Here\05_update_gitignore.ps1" -PrimeNetRoot $PrimeNetRoot
& "$Here\06_verify_cleanup.ps1" -PrimeNetRoot $PrimeNetRoot

Write-Host ""
Write-Host "[COMPLETE] Final dry-run workflow finished."
Write-Host "Review maintenance\reports before applying changes."
