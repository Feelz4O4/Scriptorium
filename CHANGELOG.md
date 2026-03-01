# Changelog

All notable changes to this repository are documented in this file.
This project follows a versioned changelog format.

## [1.1.0] - 2026-03-01

### Added

- GUI screenshots embedded in tool READMEs.
- Root `tests/` suite with `pytest` coverage for `Folio`, `Officina`, and `Versicle`.
- `.github/workflows/pytest.yml` to run tests on push and pull requests.
- Root `README.md` testing section with local and CI guidance.

### Changed

- `.gitignore` now tracks `build/*.spec` while still ignoring generated build outputs.
- Root `README.md` now includes an MIT license badge and license section.
- `Folio` is now documented as deprecated and retained as a compatibility wrapper.
- `Folio/folio.py` now forwards to `Officina/officina.py` with PNG->JPG defaults.
- `Officina` now supports `--non-recursive` (default remains recursive scanning).
- `Officina` task payload now uses a `ConversionTask` dataclass instead of a positional tuple.
- `Officina` now exits with a non-zero status for invalid input directories.
- `Versicle` PNG collection now avoids case-variant duplicate scans and uses stable resolved-path deduplication.
- `Scriptorium` Versicle tab now uses mutually exclusive write modes (`Overwrite` vs `Skip existing`).
- `Scriptorium` embedded Officina forwarding now uses a dedicated helper (`_run_officina_embedded`).
- `Officina` and `Scriptorium` versions bumped to `1.1.0`.

## [1.0.0] - 2026-02-22

### Added

- MIT `LICENSE`.
- Root `README.md` with tool index, comparison table, quick-start commands, and requirements.
- `Scriptorium/README.md` to document the unified GUI tool.
- Root `.gitignore` for Python, build, cache, logs, IDE, and OS artifacts.
- Root `requirements.txt` with shared dependencies.

### Changed

- Updated command examples in `Folio/README.md`, `Officina/README.md`, and `Versicle/README.md` to run correctly from repo root.
- Clarified `Officina` `--input` description to match actual CLI behavior.
