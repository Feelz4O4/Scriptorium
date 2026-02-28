# Scripts

![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)

A toolkit of Python utilities for batch image conversion and PNG metadata extraction.

## Tools

1. `Folio` (deprecated compatibility wrapper)  
Legacy PNG to JPG entrypoint that now forwards to `Officina` with PNG/JPG defaults.
README: `Folio/README.md`

2. `Officina`  
Parallel image converter (`jpg` or `webp`) with CLI and GUI.
README: `Officina/README.md`

3. `Versicle`  
PNG metadata extractor to Markdown sidecar files with CLI and GUI.
README: `Versicle/README.md`

4. `Scriptorium`  
Unified GUI for Officina + Versicle workflows.
README: `Scriptorium/README.md`

## Tool Comparison

| Tool | CLI | GUI | Primary Input | Primary Output | Best For |
|---|---|---|---|---|---|
| `Folio` | Yes (`folio.py`, deprecated wrapper) | No | PNG files/folders | JPG images | Backward-compatible alias for Officina PNG->JPG |
| `Officina` | Yes (`officina.py`) | Yes (`officina_gui.py`) | Images by extension filter (default `.png`, `.heic`, `.heif`; optional JPEG input) | JPG or WebP images | Faster batch conversion with quality/metadata controls |
| `Versicle` | Yes (`versicle.py`) | Yes (`versicle_gui.py`) | PNG files/folders | Same-name `.md` sidecar files with metadata | Prompt/metadata extraction from PNG assets |
| `Scriptorium` | No standalone processing CLI (GUI launcher only) | Yes (`scriptorium_gui.py`) | Shared input folder for Officina + Versicle tabs | Officina outputs and/or Versicle sidecars | One-window workflow for conversion + metadata extraction |

## Which Tool To Use

- Use `Officina` for image conversion workflows, including simple PNG to JPG runs.
- Use `Folio` only for backward compatibility with older scripts/commands.
- Use `Versicle` when you need metadata exported to Markdown sidecars.
- Use `Scriptorium` when you prefer a unified GUI for both Officina and Versicle tasks.

## Quick Start

From project root:

```bash
python .\Folio\folio.py --help
python .\Officina\officina.py --help
python .\Versicle\versicle.py --help
python .\Scriptorium\scriptorium_gui.py
```

## Requirements

- Python 3.8+
- Pillow (for image tools)
- customtkinter (for GUI tools)
- Optional: `pillow-heif` for HEIF/HEIC support in Officina

Install common dependencies:

```bash
pip install pillow customtkinter
```

Optional HEIF support:

```bash
pip install pillow-heif
```

## Testing

Run the CLI test suite from the repository root:

```bash
python -m pytest -q
```

The suite uses generated temporary files (no committed test assets) and focuses on
CLI behavior for `Folio`, `Officina`, and `Versicle`.

CI runs the same test suite on push and pull requests via:

- `.github/workflows/pytest.yml`

## License

MIT. See `LICENSE`.
