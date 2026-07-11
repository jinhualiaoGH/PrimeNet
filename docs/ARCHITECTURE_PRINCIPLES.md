# PrimeNet Architecture Principles

## 1. Infrastructure First

Build reproducible computational infrastructure before large-scale analysis.

## 2. Canonical Index Principle

Every PrimeNet repository is indexed by the prime index `i`.

## 3. Canonical Storage Principle

Each mathematical object is stored once, in its smallest lossless canonical representation.

| Object | Symbol | Storage |
|---|---:|---:|
| Prime | `p(i)` | `uint64` |
| Gap | `g(i)` | `uint16` |
| Event | `e(i)` | `uint8` |

## 4. Query, Do Not Recompute

Once a repository is verified, future tools should query it rather than regenerate it.

## 5. Direct Derived Builders

Derived repositories should be generated directly from their authoritative source in final format.

Example:

```text
Prime Repository uint64
        ↓
Gap Repository uint16
```

not

```text
Prime Repository uint64
        ↓
Gap Repository uint64
        ↓
Gap Repository uint16
```
