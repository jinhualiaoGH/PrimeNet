$ErrorActionPreference = "Stop"
$RuntimeCsv = "E:\PrimeNet\Repository\metadata\generation_runtime.csv"
$OutDir = "C:\PrimeNet\Lab\outputs\regression_plans"
if (!(Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }
py "C:\PrimeNet\Lab\regression_tests\make_regression_plan.py" --runtime-csv $RuntimeCsv --out-dir $OutDir --start 1 --end 1000000000000 --batch-size 10000000000
