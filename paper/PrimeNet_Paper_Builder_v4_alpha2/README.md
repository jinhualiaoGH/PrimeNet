# PrimeNet Paper Builder v4.0-alpha.2

This package stabilizes the executable foundation of the PrimeNet Paper Builder v4 framework.
It provides:

- typed configuration,
- structured logging,
- paper-manifest loading,
- plugin discovery,
- a deterministic foundation pipeline,
- a unified command-line interface,
- a non-destructive `doctor` diagnostic command,
- explicit setuptools package discovery,
- editable installation and automated tests,
- an initial Architecture Paper plugin.

It does **not yet** generate DOCX/PDF manuscripts. Those engines are scheduled for later implementation milestones.

## Windows installation and validation

Extract the package and open PowerShell in its directory:

```powershell
cd C:\PrimeNet\paper\PrimeNet_Paper_Builder_v4_alpha2

py -m compileall .
py -m pip install -e ".[dev]"
py -m pytest

py -m builder doctor
py -m builder --help
py -m builder --list-papers
py -m builder --paper architecture
```

Use `py -m pytest` rather than relying on a globally available `pytest` command. This guarantees that tests run with the same Python interpreter used for installation.

The final build command creates:

```text
build\architecture\<build-id>\
    build_plan.json
    FOUNDATION_READY.txt
    build_summary.json
```

A structured log is written to `logs\paper_builder.log`.

## Installed entry point

After editable installation, this is also available:

```powershell
primenet-paper doctor
primenet-paper --list-papers
primenet-paper --paper architecture
```

## Alternative script entry point

```powershell
py .\build_paper.py --paper architecture
```

## Configuration file

A JSON configuration file may override default roots:

```json
{
  "papers_root": "papers",
  "evidence_root": "evidence",
  "output_root": "build",
  "release_root": "releases",
  "log_root": "logs",
  "strict": true
}
```

Run with:

```powershell
py -m builder --config .\paper_builder.json --paper architecture
```
