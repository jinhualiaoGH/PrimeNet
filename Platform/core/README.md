# PrimeNet Platform Repository Engine

This directory is the `Platform.core` package. It is distinct from the root `core` framework package.

Run modules from `C:\PrimeNet`:

```powershell
py -m Platform.core.verify_repository --mode fast
py -m Platform.core.verify_gap_repository
py -m Platform.core.query_repository
```

Internal imports must use `from Platform.core...`.
