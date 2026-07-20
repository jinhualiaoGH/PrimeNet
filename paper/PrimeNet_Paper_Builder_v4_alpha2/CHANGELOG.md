# Changelog

## 4.0.0-alpha.2

### Fixed

- Fixed setuptools failure caused by automatic discovery of multiple top-level directories.
- Added explicit discovery of only `builder` and `builder.*` import packages.
- Restored editable installation with `py -m pip install -e ".[dev]"`.
- Updated test instructions to use `py -m pytest` for interpreter consistency.

### Added

- Added `py -m builder doctor` installation and project diagnostics.
- Added diagnostics for Python, project paths, writable runtime roots, plugins, and pytest.
- Added doctor, CLI, and packaging regression tests.

### Improved

- Improved CLI validation and maintenance-command handling.
- Updated Windows integration documentation.

## 4.0.0-alpha.1

- Added executable framework bootstrap.
- Added typed configuration model.
- Added structured console/file logging.
- Added manifest validation and plugin discovery.
- Added foundation build pipeline.
- Added unified CLI and module entry point.
- Added Architecture Paper validation plugin.
- Added initial pytest suite.
