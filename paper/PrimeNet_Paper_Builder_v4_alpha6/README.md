# PrimeNet Paper Builder v4.0-alpha.6

Alpha.6 introduces the Section Engine. The build pipeline now validates evidence, renders tables and figures, resolves typed section templates, and assembles a deterministic Markdown manuscript.

```powershell
py -m pip install -e ".[dev]"
py -m pytest
py -m builder doctor
py -m builder evidence
py -m builder --paper architecture
```

Generated architecture artifacts include `section_catalog.json`, `sections/*.md`, and `manuscript.md`.
