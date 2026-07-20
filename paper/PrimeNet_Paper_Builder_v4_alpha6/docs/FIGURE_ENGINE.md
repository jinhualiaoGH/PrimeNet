# Figure Engine v1

The Figure Engine discovers JSON figure specifications under each paper plugin's
`figures/` directory. It resolves typed evidence through the Evidence Registry and
renders deterministic, headless publication assets.

Each figure produces:

- PNG for document and preview workflows;
- SVG for scalable publication workflows;
- JSON metadata recording evidence, labels, values, and output names;
- a build-level `figure_catalog.json`.

Alpha.5 supports bar and line figures, horizontal or vertical orientation, and
linear or logarithmic value scales. Matplotlib uses the non-interactive `Agg`
backend, so builds work in PowerShell, CI, and server environments.
