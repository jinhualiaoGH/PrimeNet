$ErrorActionPreference = "Stop"
$Source = "C:\PrimeNet\Platform"
$Target = "C:\PrimeNet\Lab\Platform_v2_dev"
if (!(Test-Path $Source)) { throw "Stable platform folder not found: $Source" }
if (!(Test-Path $Target)) { New-Item -ItemType Directory -Path $Target | Out-Null }
robocopy $Source $Target /E /XD __pycache__ .git .venv venv /XF *.pyc | Out-Host
Write-Host "Copied stable Platform into Lab development folder." -ForegroundColor Green
