# ============================================================
# PrimeNet Cleanup Iteration 1
#
# SAFE CLEANUP ONLY
#
# Removes:
#   - __pycache__ directories
#   - *.pyc
#   - *.pyo
#   - Empty directories
#
# Does NOT remove any source code or project files.
# ============================================================

$ROOT = "C:\PrimeNet"

Write-Host ""
Write-Host "============================================="
Write-Host " PrimeNet Cleanup Iteration 1"
Write-Host "============================================="
Write-Host ""

# ------------------------------------------------------------
# Delete __pycache__
# ------------------------------------------------------------

Write-Host "[1/4] Removing __pycache__ directories..."

Get-ChildItem $ROOT -Directory -Recurse -Force |
Where-Object { $_.Name -eq "__pycache__" } |
ForEach-Object {

    Write-Host "Deleting $($_.FullName)"
    Remove-Item $_.FullName -Recurse -Force

}

# ------------------------------------------------------------
# Delete *.pyc
# ------------------------------------------------------------

Write-Host ""
Write-Host "[2/4] Removing *.pyc files..."

Get-ChildItem $ROOT -File -Recurse -Force -Include *.pyc |
ForEach-Object {

    Write-Host "Deleting $($_.FullName)"
    Remove-Item $_.FullName -Force

}

# ------------------------------------------------------------
# Delete *.pyo
# ------------------------------------------------------------

Write-Host ""
Write-Host "[3/4] Removing *.pyo files..."

Get-ChildItem $ROOT -File -Recurse -Force -Include *.pyo |
ForEach-Object {

    Write-Host "Deleting $($_.FullName)"
    Remove-Item $_.FullName -Force

}

# ------------------------------------------------------------
# Remove empty directories
# Repeat several passes because deleting one empty folder
# can make its parent become empty.
# ------------------------------------------------------------

Write-Host ""
Write-Host "[4/4] Removing empty directories..."

$removed = 0

do {

    $deletedThisPass = 0

    Get-ChildItem $ROOT -Directory -Recurse |
    Sort-Object FullName -Descending |
    ForEach-Object {

        $count = @(Get-ChildItem $_.FullName -Force).Count

        if ($count -eq 0) {

            Write-Host "Deleting empty folder $($_.FullName)"
            Remove-Item $_.FullName -Force

            $removed++
            $deletedThisPass++

        }

    }

} while ($deletedThisPass -gt 0)

Write-Host ""
Write-Host "============================================="
Write-Host "Cleanup complete."
Write-Host ""
Write-Host "__pycache__ removed"
Write-Host "*.pyc removed"
Write-Host "*.pyo removed"
Write-Host "Empty folders removed: $removed"
Write-Host "============================================="