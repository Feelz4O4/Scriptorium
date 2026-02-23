import argparse
import os
from pathlib import Path

from PIL import Image, ImageOps


def parse_args():
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Convert PNG files to JPG.")
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


def iter_png_files(input_dir: Path, recursive: bool, output_dir: Path):
    if recursive:
        for root, dirs, files in os.walk(input_dir, topdown=True):
            dirs[:] = [
                d
                for d in dirs
                if Path(root, d).resolve() != output_dir.resolve()
            ]
            for filename in files:
                if filename.lower().endswith(".png"):
                    yield Path(root, filename)
    else:
        for file_path in sorted(input_dir.iterdir(), key=lambda p: p.name.lower()):
            if file_path.is_file() and file_path.suffix.lower() == ".png":
                yield file_path


def main():
    args = parse_args()
    input_dir = Path(args.input).resolve()
    if not input_dir.is_dir():
        raise SystemExit(f"Input folder not found: {input_dir}")

    output_dir = Path(args.output).resolve() if args.output else input_dir / "jpg"
    output_dir.mkdir(parents=True, exist_ok=True)
    quality = max(1, min(95, args.quality))

    converted = 0
    skipped = 0
    failed = 0

    for src in iter_png_files(input_dir, args.recursive, output_dir):
        rel_dir = src.parent.relative_to(input_dir)
        dst_dir = output_dir / rel_dir
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / f"{src.stem}.jpg"

        if dst.exists() and not args.overwrite:
            print(f"Skipped {src} (already exists)")
            skipped += 1
            continue

        try:
            with Image.open(src) as img:
                fixed_img = ImageOps.exif_transpose(img)
                rgb_img = fixed_img.convert("RGB")
                rgb_img.save(dst, "JPEG", quality=quality, optimize=True)
            print(f"Converted {src}")
            converted += 1
        except OSError as exc:
            print(f"Failed {src}: {exc}")
            failed += 1

    print(
        f"Done | converted: {converted}, skipped: {skipped}, failed: {failed}, "
        f"output: {output_dir}"
    )


if __name__ == "__main__":
    main()
