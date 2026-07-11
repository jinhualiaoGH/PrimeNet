# PrimeNet Architecture

**PrimeNet: An Observatory for Prime Information Structures**

**Architecture status:** Accepted  
**Architecture generation:** 2026  
**Canonical repository scale:** 1 through 3 trillion  
**Architecture acceptance audit:** 67 / 67 checks passed

---

## 1. Purpose

PrimeNet is persistent observational infrastructure for prime arithmetic. It provides a coherent environment in which prime structures can be represented, stored, verified, queried, measured, observed, validated, reproduced, and published.

PrimeNet is not organized around one conjecture or one computation. Its central scientific principle is:

> Arithmetic may be studied through systematic observation.

---

## 2. Architectural Philosophy

PrimeNet follows four primary design principles:

> Observe. Measure. Validate. Explore.

- **Observe:** create stable access to large arithmetic structures.
- **Measure:** apply reusable scientific instruments.
- **Validate:** preserve provenance, verification, and acceptance evidence.
- **Explore:** use the verified infrastructure to investigate new structures.

---

## 3. Canonical Mathematical Coordinate System

The fundamental coordinate system of PrimeNet is the **prime index**.

Let `p(i)` denote the prime at index `i`. The outgoing gap owned by index `i` is

```text
g(i) = p(i + 1) - p(i)
```

The canonical relationship is therefore:

```text
one stored prime index i
<-> one stored prime p(i)
<-> one stored outgoing gap g(i)
```

Prime values and prime gaps are aligned observations over the same index space.

---

## 4. Left-Owned Full-Mode Gap Contract

PrimeNet uses a left-owned full-mode representation. If a prime file contains

```text
p(s), p(s + 1), ..., p(e)
```

then the corresponding gap file contains

```text
g(s), g(s + 1), ..., g(e)
```

where

```text
g(e) = p(e + 1) - p(e)
```

Thus:

```text
number of stored primes = number of stored gaps
```

---

## 5. Boundary Ownership

For adjacent prime partitions A and B, the last gap stored with A is computed using the first prime in B. The final prime in the left partition owns the boundary gap.

A file boundary is a storage boundary, not a mathematical boundary.

---

## 6. Terminal Boundary Contract

The final repository file has no following physical file. PrimeNet therefore computes the next prime directly and stores the final outgoing gap.

For the accepted 1–3T repository:

```text
final stored prime : 2,999,999,999,933
next prime         : 3,000,000,000,013
terminal gap       : 80
```

The terminal representation is mathematically complete.

---

## 7. Canonical Repository

The accepted repository covers

```text
1 through 3,000,000,000,000
```

and is stored under:

```text
E:\PrimeNet\Repository
```

Principal directories include:

```text
ranges\
gaps_u16_v3\
metadata\
logs\
observations\
```

---

## 8. Prime Repository

Prime files are stored under:

```text
E:\PrimeNet\Repository\ranges
```

They use `uint64` arrays and filenames of the form:

```text
primes_START_END.npy
```

All traversal must parse numeric range coordinates. Lexical filename ordering is never authoritative.

---

## 9. Gap Repository

Accepted gap files are stored under:

```text
E:\PrimeNet\Repository\gaps_u16_v3
```

They use `uint16` arrays and filenames of the form:

```text
gaps_START_END.npy
```

Each gap file has one-to-one range correspondence with its prime file.

---

## 10. Repository Acceptance

The accepted repository passed full arithmetic verification:

```text
Prime files                    : 300
Gap files                      : 300
Manifest rows                  : 300
Files passed                   : 300
Total primes                   : 108,340,298,703
Total gaps                     : 108,340,298,703
Local gaps verified            : 108,340,298,403
Ordinary boundaries verified  : 299
Terminal boundaries verified  : 1
Warnings                       : 0
Errors                         : 0
```

For every stored prime index:

```text
g(i) = p(i + 1) - p(i)
```

---

## 11. Top-Level Architecture

The accepted source tree is organized as:

```text
C:\PrimeNet
├── archive
├── catalog
├── config
├── core
├── docs
├── instruments
├── Lab
├── logs
├── maintenance
├── observatories
├── paper
├── Platform
├── products
├── reports
├── runs
├── scripts
└── tests
```

Each top-level directory has a distinct responsibility.

---

## 12. Architectural Layers

```text
Publication
    |
Reports
    |
Observatories
    |
Instruments
    |
Scientific Services
    |
Controlled Execution
    |
Platform
    |
Repository
    |
Canonical Mathematical Objects
```

Higher layers depend on lower layers and should not redefine lower-layer responsibilities.

---

## 13. Canonical Mathematical Objects Layer

This layer contains prime values, prime indices, prime gaps, fixed-gap events, transition structures, entropy structures, information structures, and other arithmetic observables.

The prime index remains the canonical coordinate.

---

## 14. Repository Layer

The repository layer is responsible for:

- prime and gap storage,
- partition management,
- numeric ordering,
- manifests and metadata,
- provenance,
- verification,
- and query access.

Repository correctness must be established before scientific observation begins.

---

## 15. Platform Layer

The Platform subsystem is located at:

```text
C:\PrimeNet\Platform
```

It owns repository construction, verification, range-file handling, querying, runtime summaries, configuration, and low-level production operations.

Canonical modules include:

```text
Platform\core\build_prime_range.py
Platform\core\drive_prime_repository.py
Platform\core\verify_repository.py
Platform\core\build_gap_repository.py
Platform\core\verify_gap_repository.py
Platform\core\range_files.py
Platform\core\query_repository.py
Platform\core\repository.py
Platform\core\finalize_repository.py
Platform\core\summarize_runtime.py
```

Superseded implementations are archived and excluded from the active architecture.

---

## 16. Core Scientific Service Layer

Shared services are located under:

```text
C:\PrimeNet\core
```

They provide configuration, paths, logging, repository access, product services, sessions, instruments, observatories, registries, missions, and controlled execution.

The scientific Core is distinct from the repository Platform.

---

## 17. Controlled Execution Layer

Controlled execution is located under:

```text
C:\PrimeNet\core\execution
```

It makes computation traceable, resumable, observable, and auditable. A controlled run may preserve:

```text
command.txt
heartbeat.csv
job_summary.json
stdout.log
```

Run records are stored under:

```text
C:\PrimeNet\runs
```

---

## 18. Instrument Layer

Reusable instruments are stored under:

```text
C:\PrimeNet\instruments
```

Current families include entropy, geometry, matrix, repository, runtime, spectrum, taxonomy, transition, and validation.

An instrument is a reusable measurement capability, not a complete research program.

---

## 19. Observatory Layer

Domain observatories are stored under:

```text
C:\PrimeNet\observatories
```

An observatory combines repository access, instruments, execution context, validation, and domain interpretation.

Current areas include entropy-rate, information, PNT, transition, twin primes, and validation.

---

## 20. Twin Prime Observatory

The Twin Prime Observatory is located at:

```text
C:\PrimeNet\observatories\twin_primes
```

A twin-prime event is represented by:

```text
g(i) = 2
```

The accepted 1–3T census produced:

```text
Gap files scanned   : 300
Total gaps scanned  : 108,340,298,703
Twin-prime events   : 5,173,760,785
Global twin density : 0.047754721437340
```

---

## 21. Twin Prime Validation Package

The formal package is located at:

```text
C:\PrimeNet\observatories\twin_primes\validation_package
```

It contains source data, figures, reports, tables, validation records, and a SHA-256 checksum manifest.

The canonical source observation also remains under:

```text
E:\PrimeNet\Repository\observations\twin_primes
```

---

## 22. Product Layer

Durable scientific outputs are stored under:

```text
C:\PrimeNet\products
```

Products include CSV files, JSON summaries, matrices, measurements, and validation records.

```text
Instrument  -> performs measurement
Observatory -> coordinates investigation
Product     -> preserves output
```

---

## 23. Report Layer

Formal reports are stored under:

```text
C:\PrimeNet\reports
```

Reports organize evidence for human review and communication. The architecture audit writes to:

```text
C:\PrimeNet\reports\architecture_acceptance
```

---

## 24. Publication Layer

Publication infrastructure is located under:

```text
C:\PrimeNet\paper
```

It owns manuscript construction, references, styles, figures, tables, templates, build logs, and final publication outputs.

---

## 25. Laboratory Layer

Exploratory work is located under:

```text
C:\PrimeNet\Lab
```

The Lab is experimental. Promotion from Lab to active architecture must be deliberate and accompanied by validation.

---

## 26. Configuration Layer

Configuration is stored under:

```text
C:\PrimeNet\config
C:\PrimeNet\Platform\config
```

Configuration controls execution behavior but must not redefine mathematical contracts. Historical run configurations must be distinguished from reusable defaults.

---

## 27. Catalog Layer

Catalog infrastructure is stored under:

```text
C:\PrimeNet\catalog
```

It provides structured inventory and discoverability for repositories, datasets, instruments, observatories, products, and observations.

---

## 28. Maintenance Layer

Maintenance tools are stored under:

```text
C:\PrimeNet\maintenance
```

They support architecture audits, cleanup, migration, archival operations, and structural review. Read-only auditing is preferred whenever possible.

---

## 29. Archive Policy

Superseded implementations are preserved under:

```text
C:\PrimeNet\archive
C:\PrimeNet\Platform\archive
```

Archived code is retained for provenance but is not active and must not be imported by the accepted source tree.

---

## 30. Numeric Repository Ordering

Repository order is mathematical order, not lexical order.

All tools that traverse partitioned files must parse numeric start and end coordinates explicitly. This applies to builders, verifiers, queries, observatories, and audits.

---

## 31. Separation of Mathematical and Physical Structure

PrimeNet distinguishes continuous mathematical sequences from partitioned physical storage.

```text
mathematical continuity != physical file continuity
```

Storage representation must conform to the coordinate system; the coordinate system must never conform to storage limitations.

---

## 32. Validation Architecture

Validation occurs at multiple levels:

1. source integrity,
2. import integrity,
3. architectural integrity,
4. repository integrity,
5. boundary integrity,
6. observatory integrity,
7. product integrity.

Accepted observations must be traceable to accepted repositories and validated code.

---

## 33. Architecture Acceptance Audit

The read-only audit is located at:

```text
C:\PrimeNet\maintenance\audit_primenet_architecture.py
```

Accepted version:

```text
PrimeNet Architecture Acceptance Audit v1.1.0
```

Accepted result:

```text
Checks total  : 67
Checks passed : 67
Checks failed : 0

[ACCEPTED]
PrimeNet satisfies the current architecture contract.
```

---

## 34. Source-Tree Cleanliness

The active tree excludes generated artifacts and obsolete references, including:

```text
__pycache__/
*.pyc
```

The architecture also prohibits malformed imports, active dependencies on archived modules, duplicate canonical implementations, and ambiguous repository ordering.

---

## 35. Namespace Policy

PrimeNet uses explicit package namespaces:

```text
core.*
Platform.core.*
instruments.*
observatories.*
```

Platform modules use `Platform.core.*` when imported from the PrimeNet root. Scientific services use canonical top-level namespaces.

---

## 36. Provenance

PrimeNet treats provenance as a first-class requirement. Scientific computations should preserve enough evidence to determine:

- what was executed,
- which repository and configuration were used,
- when the computation ran,
- what outputs were produced,
- whether it completed,
- and what validation evidence exists.

---

## 37. Reproducibility

A PrimeNet result should be reconstructible from:

```text
accepted repository
+
canonical source
+
configuration
+
execution provenance
+
validation evidence
```

Reproducibility is part of the architecture, not an afterthought.

---

## 38. Current Accepted Baseline

```text
Canonical prime repository : 1 through 3T
Canonical gap repository   : left-owned full-mode uint16
Prime files                : 300
Gap files                  : 300
Stored primes              : 108,340,298,703
Stored gaps                : 108,340,298,703
Ordinary boundaries        : 299 verified
Terminal boundaries        : 1 verified
Warnings                    : 0
Errors                      : 0
Twin-prime events           : 5,173,760,785
Global twin density         : 0.047754721437340
Architecture audit          : 67 / 67 passed
```

---

## 39. Architectural Invariants

1. The prime index is the canonical coordinate.
2. `g(i) = p(i + 1) - p(i)`.
3. Every stored prime index owns one outgoing gap.
4. The number of stored primes equals the number of stored gaps.
5. Physical boundaries do not alter arithmetic continuity.
6. Repository files are ordered mathematically, never lexically.
7. Platform infrastructure is distinct from scientific Core services.
8. Instruments provide reusable measurements.
9. Observatories coordinate domain-specific investigations.
10. Accepted observations preserve provenance and validation evidence.

---

## 40. Architectural Direction

PrimeNet is intended to grow incrementally through new repository scales, instruments, observatories, event languages, validation systems, products, reports, and publications.

New capabilities must be placed in the proper architectural layer rather than creating parallel or ambiguous infrastructure.

---

## 41. PrimeNet Scientific Model

```text
Prime Arithmetic
       |
Canonical Index Coordinates
       |
Verified Repositories
       |
Controlled Execution
       |
Reusable Instruments
       |
Domain Observatories
       |
Scientific Products
       |
Validation
       |
Reports
       |
Publications
       |
New Questions
```

New observations generate new questions, and new questions generate new instruments and observatories.

---

## 42. Conclusion

PrimeNet establishes a unified architecture for large-scale observational prime arithmetic.

Its foundation is the prime index as the canonical coordinate system. Its repository preserves aligned prime and gap objects. Its Platform provides verified computational infrastructure. Its Core provides scientific services. Its Instruments measure arithmetic structures. Its Observatories coordinate investigations. Controlled execution preserves provenance. Validation establishes trust. Reports and publications communicate results.

Together, these components implement the PrimeNet principle:

> Observe. Measure. Validate. Explore.

PrimeNet is designed to provide the infrastructure from which discoveries may emerge.
