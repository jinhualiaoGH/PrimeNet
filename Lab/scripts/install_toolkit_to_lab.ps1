$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $Here
& "$Here\00_create_lab_structure.ps1"
Copy-Item "$Root\tools\analyze_runtime.py" "C:\PrimeNet\Lab\runtime_analysis\analyze_runtime.py" -Force
Copy-Item "$Root\tools\expected_file_verifier.py" "C:\PrimeNet\Lab\verifier_tests\expected_file_verifier.py" -Force
Copy-Item "$Root\tools\make_regression_plan.py" "C:\PrimeNet\Lab\regression_tests\make_regression_plan.py" -Force
Copy-Item "$Root\tools\lab_notebook.py" "C:\PrimeNet\Lab\notes\lab_notebook.py" -Force
Copy-Item "$Root\config\lab_config.json" "C:\PrimeNet\Lab\lab_config.json" -Force
Write-Host "PrimeNet Lab Toolkit installed into C:\PrimeNet\Lab" -ForegroundColor Green
