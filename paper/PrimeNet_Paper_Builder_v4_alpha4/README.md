# PrimeNet Paper Builder v4.0-alpha.3

Alpha.3 introduces the typed Evidence Engine while retaining the validated alpha.2 framework foundation.

## Windows validation

```powershell
py -m compileall .
py -m pip install -e ".[dev]"
py -m pytest
py -m builder doctor
py -m builder evidence
py -m builder --list-papers
py -m builder --paper architecture
```

The architecture build now emits:

- `evidence_validation.txt`
- `evidence_catalog.json`
- `build_plan.json`
- `EVIDENCE_ENGINE_READY.txt`
- `build_summary.json`

See `docs/EVIDENCE_ENGINE.md` for the evidence package contract.
