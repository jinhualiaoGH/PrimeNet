# PrimeNet Python Namespace Contract

PrimeNet has two intentionally separate Python layers.

## Framework layer

Package: `core`

Location: `C:\PrimeNet\core`

Responsibilities: sessions, logging, paths, registry, observatory and instrument abstractions, missions, products, and the framework-facing repository service.

Run framework commands from `C:\PrimeNet`, for example:

```powershell
cd C:\PrimeNet
py -m core.session
```

## Repository engine layer

Package: `Platform.core`

Location: `C:\PrimeNet\Platform\core`

Responsibilities: prime and gap construction, repository verification, finalization, query services, range-file topology, and production execution.

Run repository-engine commands from `C:\PrimeNet`, for example:

```powershell
cd C:\PrimeNet
py -m Platform.core.verify_repository --mode fast
py -m Platform.core.drive_prime_repository --config Platform/config/repository_build.yaml
```

## Rule

Active Platform modules must import one another through `Platform.core`, never through the top-level `core` package. This prevents the framework package and repository-engine package from resolving differently according to the current working directory.
