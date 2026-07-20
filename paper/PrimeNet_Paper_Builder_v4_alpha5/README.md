# PrimeNet Paper Builder v4.0-alpha.5

An evidence-driven scientific publication framework for PrimeNet.

Alpha.5 provides the Framework Foundation, Evidence Engine v1, Table Engine v1,
and Figure Engine v1. The architecture plugin demonstrates deterministic table
and figure generation from the same canonical evidence record.

## Integration

```powershell
py -m compileall .
py -m pip install -e ".[dev]"
py -m pytest
py -m builder doctor
py -m builder evidence
py -m builder --paper architecture
```

The architecture build emits evidence validation, table and figure catalogs,
PNG/SVG figure assets, Markdown/CSV/JSON tables, a build plan, and a summary.
