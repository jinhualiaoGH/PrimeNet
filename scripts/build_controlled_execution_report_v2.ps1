Write-Host "============================================================"
Write-Host "PrimeNet Controlled Execution Benchmark Report v2 Builder"
Write-Host "============================================================"

$SRC = "C:\PrimeNet\runs\20260708_203236_primenet_2T_3T_full"
$ANALYSIS = "C:\PrimeNet_Controlled_Execution_Benchmark_Analysis_v2"
$OUT = "C:\PrimeNet\reports\controlled_execution_benchmark_v2"

New-Item -ItemType Directory -Force -Path $OUT | Out-Null
New-Item -ItemType Directory -Force -Path "$OUT\evidence" | Out-Null
New-Item -ItemType Directory -Force -Path "$OUT\figures" | Out-Null
New-Item -ItemType Directory -Force -Path "$OUT\tables" | Out-Null
New-Item -ItemType Directory -Force -Path "$OUT\report" | Out-Null

Write-Host "[1/4] Running benchmark analysis v2..."
cd $ANALYSIS
py benchmark_analysis_v2.py `
  --run-dir $SRC `
  --out-dir "$OUT\analysis_outputs"

Write-Host "[2/4] Copying evidence files..."
Copy-Item "$SRC\job_summary.json" "$OUT\evidence\" -Force
Copy-Item "$SRC\heartbeat.csv" "$OUT\evidence\" -Force
Copy-Item "$SRC\stdout.log" "$OUT\evidence\" -Force
Copy-Item "$SRC\stderr.log" "$OUT\evidence\" -Force
Copy-Item "$SRC\environment.json" "$OUT\evidence\" -Force
Copy-Item "$SRC\command.txt" "$OUT\evidence\" -Force

Write-Host "[3/4] Copying analysis outputs..."
Copy-Item "$OUT\analysis_outputs\*.json" "$OUT\evidence\" -Force
Copy-Item "$OUT\analysis_outputs\*.csv" "$OUT\tables\" -Force
Copy-Item "$OUT\analysis_outputs\figures\*.png" "$OUT\figures\" -Force
Copy-Item "$OUT\analysis_outputs\*.md" "$OUT\report\" -Force

Write-Host "[4/4] Creating manifest..."
$manifest = @{
  package = "PrimeNet Controlled Execution Benchmark Report v2"
  created_at = (Get-Date).ToString("s")
  source_run = $SRC
  output_dir = $OUT
  campaign = "2T to 3T"
  principle = "Observe the primes. Measure the computation. Validate the evidence. Trust the result."
}
$manifest | ConvertTo-Json -Depth 5 | Out-File "$OUT\manifest.json" -Encoding utf8

Write-Host "============================================================"
Write-Host "Report package complete:"
Write-Host $OUT
Write-Host "============================================================"