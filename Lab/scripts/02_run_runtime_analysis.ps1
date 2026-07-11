$ErrorActionPreference = "Stop"
$RuntimeCsv = "E:\PrimeNet\Repository\metadata\generation_runtime.csv"
$OutDir = "C:\PrimeNet\Lab\outputs\runtime_analysis"
if (!(Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }
py "C:\PrimeNet\Lab\runtime_analysis\analyze_runtime.py" --runtime-csv $RuntimeCsv --out-dir $OutDir --anomaly-threshold 30 --critical-threshold 60
