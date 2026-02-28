# folio

`folio.py` is deprecated and now acts as a compatibility wrapper that forwards to `Officina`.
It keeps the old Folio arguments but runs `Officina/officina.py` under the hood with:

- `--output-format jpg`
- `--ext .png`
- `--workers 1`
- `--preset photo`
- `--quality <folio --quality>`
- `--non-recursive` by default (or `--recursive` when requested)

For new usage, prefer calling `Officina` directly.

## Usage

From project root (input = script folder, output = `<input>/jpg`):

```bash
python .\Folio\folio.py
```

Direct Officina equivalent:

```bash
python .\Officina\officina.py --ext .png --output-format jpg --workers 1 --preset photo --non-recursive
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
