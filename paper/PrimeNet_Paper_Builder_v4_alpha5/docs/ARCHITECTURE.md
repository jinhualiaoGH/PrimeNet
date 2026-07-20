# Foundation Architecture

The alpha.1 runtime flow is:

```text
CLI -> Configuration -> Application -> Plugin Loader -> Pipeline -> Build Summary
```

The framework is paper-independent. Each paper is represented by a directory under `papers/` containing a `paper.json` manifest.

The alpha.1 pipeline contains three executable foundation stages:

1. `validate` checks declared evidence.
2. `plan` writes a machine-readable build plan.
3. `summarize` writes a successful foundation marker.

Future engines will register additional stages without changing paper discovery.
