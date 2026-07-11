# PrimeNet Observatory Factory v2

Version: 2.0

Status: Draft

---

# PrimeNet Observatory Factory v2

## Purpose

The PrimeNet Observatory Factory is responsible for creating observatory
instances from the Observatory Registry.

The Factory separates observatory discovery from observatory execution.

The Registry discovers observatories.

The Factory creates observatory objects.

The observatory performs scientific work.

---

# Design Goals

The Factory shall

* create observatories automatically

* require no hardcoded registration

* support future plug-in observatories

* isolate object construction

* simplify application code

---

# Overall Architecture

```
Repository
        ↓

Registry
        ↓

Observatory Catalog
        ↓

Observatory Factory
        ↓

Observatory Instance
        ↓

Products
```

Each layer has one responsibility.

---

# Responsibilities

The Factory shall

* locate observatory packages

* dynamically import observatory modules

* instantiate observatory classes

* provide dependency injection

* report creation errors

* hide implementation details from callers

---

# Factory Interface

Example:

```python
factory = PrimeNetObservatoryFactory()

transition = factory.create("transition")

entropy = factory.create("entropy_rate")
```

The caller never imports observatory modules directly.

---

# Discovery Flow

```
Registry

        ↓

observatory_catalog.json

        ↓

Factory

        ↓

Locate package

        ↓

Import module

        ↓

Instantiate observatory

        ↓

Return object
```

---

# Creation Flow

For every observatory

```
Read catalog entry

↓

Read module name

↓

Import module

↓

Locate observatory class

↓

Instantiate

↓

Return instance
```

---

# Dependency Injection

The Factory may inject

* PrimeNet Session

* Product Service

* Repository Service

* Configuration

without the caller knowing implementation details.

Example

```
factory.create(
    "transition",
    session=session
)
```

---

# Error Handling

The Factory shall detect

* unknown observatory

* missing module

* missing class

* constructor failure

* dependency failure

Errors should be reported with informative messages.

---

# Registry Relationship

The Factory never scans directories.

The Registry performs discovery.

The Factory consumes Registry information.

Responsibilities remain separate.

---

# Observatory Lifecycle

```
Registry

↓

Factory

↓

Observatory

↓

prepare()

↓

measure()

↓

validate()

↓

generate_products()

↓

completed
```

---

# Future Extension

Future versions may support

* external plug-ins

* optional observatories

* lazy loading

* distributed execution

* parallel observatory execution

without changing application code.

---

# Design Principles

The Factory

does not perform science.

does not compute measurements.

does not produce products.

Its only responsibility is creating observatory objects.

---

# Benefits

Factory v2 provides

✓ automatic observatory creation

✓ clean separation of concerns

✓ simplified application code

✓ plug-in architecture

✓ future scalability

✓ easier testing

---

# PrimeNet Philosophy

The Registry discovers.

The Factory creates.

The Observatory investigates.

The Instruments measure.

The Products preserve.

Each component has one responsibility.
