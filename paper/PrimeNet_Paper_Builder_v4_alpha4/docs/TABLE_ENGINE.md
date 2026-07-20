# Table Engine v1

The Table Engine converts validated evidence into deterministic publication tables.

Each paper plugin may provide JSON specifications under `papers/<paper>/tables/`. A specification selects an evidence ID, declares ordered columns, and assigns formatting rules. Every rendered table produces Markdown, CSV, and canonical JSON artifacts plus a build-level `table_catalog.json`.

The engine never reads repository files directly. It consumes records already registered and validated by the Evidence Engine.
