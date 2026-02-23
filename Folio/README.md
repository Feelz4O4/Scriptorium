# folio

`folio.py` converts `.png` images to `.jpg`.

## Usage

From project root (input = script folder, output = `<input>/jpg`):

```bash
python .\Folio\folio.py
```

Recursive conversion:

```bash
python .\Folio\folio.py --recursive
```

Custom paths and quality:

```bash
python .\Folio\folio.py --input "C:\path\to\pngs" --output "C:\path\to\jpgs" --quality 90
```

Overwrite existing outputs:

```bash
python .\Folio\folio.py --overwrite
```

If you run commands from inside the `Folio` folder, you can use `python folio.py ...`.

## CLI Arguments

- `--input`: Input folder to scan
- `--output`: Output folder (default: `<input>/jpg`)
- `--quality`: JPEG quality `1-95` (default: `90`)
- `--overwrite`: Overwrite existing output files
- `--recursive`: Walk subfolders and preserve structure in output
