$ErrorActionPreference = "Stop"
$LabRoot = "C:\PrimeNet\Lab"
$Dirs = @(
    $LabRoot,
    "$LabRoot\Platform_v2_dev",
    "$LabRoot\runtime_analysis",
    "$LabRoot\regression_tests",
    "$LabRoot\verifier_tests",
    "$LabRoot\benchmark",
    "$LabRoot\outputs",
    "$LabRoot\outputs\runtime_analysis",
    "$LabRoot\outputs\regression_plans",
    "$LabRoot\outputs\verifier_reports",
    "$LabRoot\notes",
    "$LabRoot\archive"
)
foreach ($d in $Dirs) {
    if (!(Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null }
}
Write-Host "PrimeNet Lab structure created at $LabRoot" -ForegroundColor Green
