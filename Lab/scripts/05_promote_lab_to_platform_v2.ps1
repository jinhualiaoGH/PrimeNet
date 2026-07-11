$ErrorActionPreference = "Stop"
$Stable = "C:\PrimeNet\Platform"
$Lab = "C:\PrimeNet\Lab\Platform_v2_dev"
$ArchiveRoot = "C:\PrimeNet\archive"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Backup = Join-Path $ArchiveRoot "Platform_v1_backup_$Stamp"
if (!(Test-Path $Lab)) { throw "Lab platform not found: $Lab" }
if (!(Test-Path $ArchiveRoot)) { New-Item -ItemType Directory -Path $ArchiveRoot | Out-Null }
Write-Host "This will backup current Platform and copy Lab version into Platform." -ForegroundColor Yellow
$confirm = Read-Host "Type PROMOTE to continue"
if ($confirm -ne "PROMOTE") { Write-Host "Promotion cancelled."; exit 0 }
robocopy $Stable $Backup /E /XD __pycache__ .git .venv venv /XF *.pyc | Out-Host
robocopy $Lab $Stable /E /XD __pycache__ .git .venv venv /XF *.pyc | Out-Host
Write-Host "Promotion complete. Backup saved at $Backup" -ForegroundColor Green
