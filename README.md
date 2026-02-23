# Scripts

![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)

A toolkit of Python utilities for batch image conversion and PNG metadata extraction.

## Tools

1. `Folio`  
PNG to JPG converter.
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
| `Folio` | Yes (`folio.py`) | No | PNG files/folders | JPG images | Simple PNG to JPG conversion |
| `Officina` | Yes (`officina.py`) | Yes (`officina_gui.py`) | Images by extension filter (default `.png`, `.heic`, `.heif`; optional JPEG input) | JPG or WebP images | Faster batch conversion with quality/metadata controls |
| `Versicle` | Yes (`versicle.py`) | Yes (`versicle_gui.py`) | PNG files/folders | Same-name `.md` sidecar files with metadata | Prompt/metadata extraction from PNG assets |
| `Scriptorium` | No standalone processing CLI (GUI launcher only) | Yes (`scriptorium_gui.py`) | Shared input folder for Officina + Versicle tabs | Officina outputs and/or Versicle sidecars | One-window workflow for conversion + metadata extraction |

## Which Tool To Use

- Use `Folio` when you only need straightforward PNG to JPG conversion.
- Use `Officina` when you need speed, WebP support, metadata/ICC/EXIF control, or size-capping.
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

## License

MIT. See `LICENSE`.
