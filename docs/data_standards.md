# PrimeNet Data Standards

## Version 1.0

---

# Purpose

PrimeNet is designed as a long-term scientific observatory for prime information structures.

To ensure reproducibility, interoperability, and long-term maintainability, every dataset generated within PrimeNet follows standardized formats and metadata conventions.

These standards apply to all observatories, computational instruments, and public releases.

---

# General Principles

Every dataset should be:

* Reproducible
* Self-describing
* Machine readable
* Human readable
* Version controlled
* Immutable after release

Released datasets should never be modified. Corrections are issued through new versions.

---

# Repository Organization

```text
repository/

├── raw_primes/
├── processed/
├── metadata/
└── releases/
```

---

# Raw Prime Data

Raw prime datasets contain only prime numbers.

Recommended format:

```
NumPy (.npy)
```

Example:

```
primes_100000000001_110000000000.npy
```

Naming convention:

```
primes_<start>_<end>.npy
```

Each file should contain:

* increasing order
* no duplicates
* verified integrity

---

# Metadata

Every released dataset should have accompanying metadata.

Example:

```json
{
    "dataset":"primes",
    "start":100000000001,
    "end":110000000000,
    "prime_count":411805481,
    "created":"2026-06-24",
    "generator":"PrimeNet Repository",
    "version":"1.0",
    "checksum":"..."
}
```

---

# CSV Standards

CSV files shall use:

* UTF-8 encoding
* comma delimiter
* header row
* decimal point notation
* no merged cells
* no hidden columns

Missing values should be represented consistently.

---

# Standard Naming Convention

```
PN###_<description>.csv
```

Examples:

```
PN021_transition_matrix.csv

PN072_information_spectrum.csv

PN101_candidate_invariants.csv
```

---

# Figures

Preferred formats:

```
PNG
PDF
SVG
```

Naming convention:

```
Fig01_entropy_spectrum.png

Fig02_transition_network.png
```

---

# Tables

Publication tables should use

```
Table01

Table02

...
```

Machine-readable tables should remain CSV.

---

# Event Languages

Binary event languages use

```
0 = event absent

1 = event present
```

Stored as

```
NumPy arrays (.npy)
```

Example:

```
events_gap_006.npy

events_gap_012.npy

events_gap_210.npy
```

---

# Transition Matrices

Rows represent source states.

Columns represent destination states.

Each row should satisfy

```
Σ P(i→j) = 1
```

within numerical precision.

---

# Entropy Measurements

Standard notation:

```
H0

H1

H2

H3

H4

H5
```

Units:

```
bits per event
```

Derived quantities:

```
Information Gain

Mutual Information

Conditional Entropy

Cross Entropy

Perplexity
```

---

# Geometry Measurements

Recommended variables:

```
I(g)

R(g)

M(g)

κ(g)
```

where

* I = Information coordinate
* R = Residual
* M = Mode component
* κ = Curvature

---

# Versioning

PrimeNet follows semantic versioning.

```
Major.Minor.Patch
```

Example:

```
1.0.0

1.1.0

2.0.0
```

Major versions may introduce new observatories.

Minor versions add new instruments.

Patch versions correct implementation issues.

---

# Reproducibility Requirements

Every published computational result should specify:

* software version
* dataset version
* input files
* execution command
* random seed (if applicable)
* runtime information

---

# Quality Assurance

Before release, every dataset should be verified for:

* completeness
* numerical consistency
* reproducibility
* documentation
* checksum validation

---

# Long-Term Compatibility

Future versions of PrimeNet should preserve backward compatibility whenever practical.

Deprecated formats should remain readable whenever possible.

Scientific data should remain accessible for future computational studies.

---

# Guiding Principle

Scientific observations become valuable only when future researchers can reproduce, verify, and extend them.

These standards ensure that PrimeNet datasets remain reliable scientific resources for years to come.
