# Changelog

## 4.0.0-alpha.3

### Added
- Typed Evidence Engine models for metrics, tables, figures, text, and datasets.
- Evidence package discovery and JSON/CSV/text/binary loading.
- Global evidence registry with duplicate-ID protection.
- Source, checksum, dependency, and readability validation.
- Deterministic evidence catalog generation.
- `primenet-paper evidence` diagnostics command.
- Evidence stage in the architecture-paper pipeline.
- Canonical 1T architecture baseline evidence package.
- Evidence Engine tests and documentation.

### Changed
- Paper manifests now declare required evidence by stable evidence ID.
- Architecture paper plugin version advanced to 0.2.0.

## 4.0.0-alpha.2

### Fixed
- Explicit setuptools package discovery.
- Editable installation and Windows developer setup.

### Added
- Doctor command and packaging regression tests.

## 4.0.0-alpha.4

### Added
- Deterministic Table Engine v1.
- JSON table specifications scoped to paper plugins.
- Markdown, CSV, and canonical JSON table output.
- Build-level table catalog.
- Architecture repository overview table.
- Table Engine regression tests.
