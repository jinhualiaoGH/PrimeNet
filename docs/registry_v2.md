# PrimeNet Registry v2

## Purpose

The PrimeNet Registry is responsible for automatic discovery of all
observatories available in the PrimeNet platform.

No observatory should require manual registration.

---

## Discovery Rules

The Registry scans

```
observatories/
```

Each immediate subdirectory is considered a candidate observatory.

A valid observatory package contains:

```
metadata.py
observatory.yaml
```

Optionally

```
*_observatory.py
```

---

## Metadata

metadata.py provides

- Observatory ID
- Name
- Version
- Category
- Description
- Supported Instruments

---

## Configuration

observatory.yaml provides

- observatory
- products
- dependencies
- status

---

## Registry Responsibilities

The Registry shall

- discover observatories

- validate package structure

- read metadata

- read yaml

- detect duplicate IDs

- detect duplicate names

- report invalid packages

- build Observatory Catalog

---

## Design Goal

Adding a new observatory should require only creating a new package under

```
observatories/
```

No registry modification should be required.