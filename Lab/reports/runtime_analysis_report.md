# PrimeNet Runtime Analysis
Source: `E:\PrimeNet\Repository\logs\builder_runtime.csv`
Success rows: **100**
Skipped existing rows: **0**
## Longest batch
- Range: **180,000,000,001 - 190,000,000,000**
- Runtime: **125.731757 minutes** (7543.905 sec)
- Output: `E:\PrimeNet\Repository\ranges\primes_180000000001_190000000000.npy`

## Batches above threshold
- 180,000,000,001 - 190,000,000,000: 125.731757 min
- 130,000,000,001 - 140,000,000,000: 51.159366 min
- 90,000,000,001 - 100,000,000,000: 46.227986 min
- 660,000,000,001 - 670,000,000,000: 43.122870 min

Recommended next step: rerun the longest batch in `C:\PrimeNet\Lab` output space before changing production code.
