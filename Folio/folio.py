import argparse
import subprocess
import sys
from pathlib import Path


def parse_args():
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Deprecated compatibility wrapper for PNG->JPG conversion.",
    )
    parser.add_argument(
        "--input",
        default=str(script_dir),
        help="Input folder to scan (default: script folder).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help='Output folder (default: "<input>/jpg").',
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=90,
        help="JPEG quality 1-95 (default: 90).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Process input subfolders recursively.",
    )
    return parser.parse_args()


def _resolve_officina_script() -> Path:
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir.parent / "Officina" / "officina.py",
        script_dir / "officina.py",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise SystemExit("Could not locate Officina/officina.py for forwarding.")


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input).resolve()
    if not input_dir.is_dir():
        raise SystemExit(f"Input folder not found: {input_dir}")

    print(
        "[DEPRECATED] Folio is now a compatibility wrapper around Officina. "
        "Prefer: python .\\Officina\\officina.py ..."
    )

    cmd = [
        sys.executable,
        str(_resolve_officina_script()),
        "--input",
        str(input_dir),
        "--output-format",
        "jpg",
        "--ext",
        ".png",
        "--workers",
        "1",
        "--preset",
        "photo",
        # We intentionally cap at 95: Pillow treats >95 as special high-quality
        # mode with diminishing returns and much larger files.
        "--quality",
        str(max(1, min(95, args.quality))),
    ]
    if args.output:
        cmd += ["--output", str(Path(args.output).resolve())]
    if args.overwrite:
        cmd.append("--overwrite")
    if args.recursive:
        cmd.append("--recursive")
    else:
        cmd.append("--non-recursive")

    proc = subprocess.run(cmd)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
