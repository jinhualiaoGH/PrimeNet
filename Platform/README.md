# PrimeNet Gap Repository v2.0 Package

This package contains the canonical direct `uint16` gap repository driver.

## File

Copy:

```text
core/drive_gap_repository.py
```

to:

```text
C:\PrimeNet\Platform\core\drive_gap_repository.py
```

## Run

```powershell
cd C:\PrimeNet\Platform
py -m core.drive_gap_repository
```

## Output

The driver reads:

```text
E:\PrimeNet\Repository\ranges\primes_*.npy
```

and writes final canonical gap files directly:

```text
E:\PrimeNet\Repository\gaps_u16\gaps_*.npy
```

No intermediate `uint64` gap repository is created.

## Notes

- Prime Repository stores `p(i)` as `uint64`.
- Gap Repository stores `g(i)=p(i+1)-p(i)` as `uint16`.
- The driver checks that max gap fits inside `uint16`.
- Cross-partition gaps are included by reading the first prime of the next partition.
