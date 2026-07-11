$ErrorActionPreference = "Stop"
$RangesDir = "E:\PrimeNet\Repository\ranges"
$OutDir = "C:\PrimeNet\Lab\outputs\verifier_reports"
if (!(Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }
py "C:\PrimeNet\Lab\verifier_tests\expected_file_verifier.py" --ranges-dir $RangesDir --start 1 --end 1000000000000 --batch-size 10000000000 --out-dir $OutDir
