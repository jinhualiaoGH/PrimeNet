# PrimeNet Twin Prime Census: 1-3T

## Formal Census and Validation Report

**Instrument:** PrimeNet Twin Prime Census v1.0.0  
**Event definition:** `g(i) = 2`  
**Repository status:** ACCEPTED  
**Numeric domain:** 1 to 3,000,000,000,000  
**Validation status:** PASSED

## Executive result

PrimeNet observed **5,173,760,785 twin-prime events** among **108,340,298,703 prime-indexed outgoing gaps** across the accepted 1-3T repository.

The global twin-event density is:

`0.047754721437340`

## Provenance

The census was performed only after the underlying index-aligned gap repository passed full acceptance:

- 300 prime files and 300 corresponding gap files
- 300/300 files passed
- 108,340,298,403 local gaps verified directly
- 299 ordinary cross-file boundaries verified
- 1 terminal boundary verified
- 0 warnings and 0 errors

The accepted repository contract is:

`g(i) = p(i + 1) - p(i)` for every stored prime index `i`.

## Validation results

All package-level validation checks passed:

- exact partition count and sequence
- contiguous numeric range ordering
- exact reconstruction of total gap count
- exact reconstruction of twin-event count
- exact reconstruction of cumulative counts
- independent recomputation of local and cumulative densities
- consistency with the canonical summary JSON

## Scale summary

| Upper bound | Partitions | Cumulative gaps | Cumulative twins | Twin density |
|---:|---:|---:|---:|---:|
| 100,000,000,000 | 10 | 4,118,054,813 | 224,376,048 | 0.054485930418 |
| 500,000,000,000 | 50 | 19,308,136,142 | 986,222,314 | 0.051078069201 |
| 1,000,000,000,000 | 100 | 37,607,912,018 | 1,870,585,220 | 0.049739140506 |
| 2,000,000,000,000 | 200 | 73,301,896,139 | 3,552,770,943 | 0.048467654046 |
| 3,000,000,000,000 | 300 | 108,340,298,703 | 5,173,760,785 | 0.047754721437 |

## Partition behavior

The first 10B partition has local twin density `0.060240693848`.  
The final 10B partition has local twin density `0.045962623212`.

The partition-level density declines gradually with numeric scale, while the cumulative twin count continues to grow monotonically. This package reports the measured census and does not claim a proof concerning the infinitude or asymptotic law of twin primes.

## Package contents

- immutable source CSV and JSON observations
- independent validation results in JSON and text
- repository acceptance provenance
- scale and key-result tables
- four publication-quality figures
- Excel analysis workbook
- Markdown and PDF reports
- SHA-256 checksum manifest

## Scientific interpretation

This census is the first scientific observation extracted from the formally accepted PrimeNet 1-3T index-coordinate repository. Twin-prime events arise as a direct observable state of the canonical gap sequence:

`T = { i : g(i) = 2 }`

No special-purpose twin-prime database is required; the observable is selected directly from the verified gap coordinate system.
