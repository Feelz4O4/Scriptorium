#!/usr/bin/env python3
"""
Extract selected PNG text metadata keys into a Markdown file.

For each PNG file, writes a sibling .md file with the same base name
containing these keys if present:
- parameters
- postprocessing
- extras
"""

from __future__ import annotations

import argparse
import struct
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, Sequence


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
TARGET_KEYS = ("parameters", "postprocessing", "extras")


def _parse_text_chunk(data: bytes) -> tuple[str, str] | None:
    if b"\x00" not in data:
        return None
    key_raw, value_raw = data.split(b"\x00", 1)
    try:
        key = key_raw.decode("latin-1")
        value = value_raw.decode("latin-1")
    except UnicodeDecodeError:
        return None
    return key, value


def _parse_ztxt_chunk(data: bytes) -> tuple[str, str] | None:
    if b"\x00" not in data:
        return None
    key_raw, rest = data.split(b"\x00", 1)
    if not rest:
        return None
    compression_method = rest[0]
    compressed_text = rest[1:]
    if compression_method != 0:
        return None
    try:
        value_raw = zlib.decompress(compressed_text)
        key = key_raw.decode("latin-1")
        value = value_raw.decode("latin-1")
    except (UnicodeDecodeError, zlib.error):
        return None
    return key, value


def _parse_itxt_chunk(data: bytes) -> tuple[str, str] | None:
    # Format: keyword\0 compression_flag compression_method language_tag\0
    # translated_keyword\0 text
    try:
        pos = data.index(b"\x00")
    except ValueError:
        return None

    key_raw = data[:pos]
    remainder = data[pos + 1 :]
    if len(remainder) < 2:
        return None

    compression_flag = remainder[0]
    compression_method = remainder[1]
    remainder = remainder[2:]

    try:
        pos = remainder.index(b"\x00")
        remainder = remainder[pos + 1 :]  # skip language tag
        pos = remainder.index(b"\x00")
        text_raw = remainder[pos + 1 :]  # skip translated keyword
    except ValueError:
        return None

    try:
        key = key_raw.decode("latin-1")
        if compression_flag == 1:
            if compression_method != 0:
                return None
            text_raw = zlib.decompress(text_raw)
        value = text_raw.decode("utf-8")
    except (UnicodeDecodeError, zlib.error):
        return None

    return key, value


def extract_png_text_metadata(path: Path) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    with path.open("rb") as f:
        if f.read(8) != PNG_SIGNATURE:
            raise ValueError(f"{path} is not a valid PNG file.")

        while True:
            length_bytes = f.read(4)
            if len(length_bytes) < 4:
                break
            (length,) = struct.unpack(">I", length_bytes)
            chunk_type = f.read(4)
            chunk_data = f.read(length)
            _crc = f.read(4)

            if len(chunk_type) < 4 or len(chunk_data) < length:
                break

            result = None
            if chunk_type == b"tEXt":
                result = _parse_text_chunk(chunk_data)
            elif chunk_type == b"zTXt":
                result = _parse_ztxt_chunk(chunk_data)
            elif chunk_type == b"iTXt":
                result = _parse_itxt_chunk(chunk_data)

            if result is not None:
                key, value = result
                metadata[key] = value

            if chunk_type == b"IEND":
                break

    return metadata


def _fenced_block(value: str) -> list[str]:
    # Choose a fence that cannot collide with content.
    max_tildes = 0
    current = 0
    for ch in value:
        if ch == "~":
            current += 1
            if current > max_tildes:
                max_tildes = current
        else:
            current = 0
    fence = "~" * max(3, max_tildes + 1)
    return [f"{fence}text", value, fence]


def _default_key_values(metadata: Dict[str, str]) -> Dict[str, str]:
    casefolded = {k.lower(): v for k, v in metadata.items()}
    return {key: casefolded.get(key, "") for key in TARGET_KEYS}


def write_markdown(
    png_path: Path,
    metadata: Dict[str, str],
    all_tags: bool,
    overwrite: bool,
) -> tuple[Path, bool]:
    md_path = png_path.with_suffix(".md")
    if md_path.exists() and not overwrite:
        return md_path, False

    lines = [f"# {png_path.name}", ""]

    keys_to_write: Sequence[str]
    if all_tags:
        keys_to_write = sorted(metadata.keys(), key=str.lower)
        value_lookup = metadata
    else:
        keys_to_write = TARGET_KEYS
        value_lookup = _default_key_values(metadata)

    if all_tags and not keys_to_write:
        lines.append("_No metadata tags found_")
        lines.append("")

    for key in keys_to_write:
        lines.append(f"## {key}")
        lines.append("")
        value = value_lookup.get(key, "")
        if value:
            lines.extend(_fenced_block(value))
        else:
            lines.append("_Not found_")
        lines.append("")

    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return md_path, True


def iter_png_files(inputs: Iterable[str], recursive: bool) -> Iterable[Path]:
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            pattern = "**/*" if recursive else "*"
            yield from sorted(
                (f for f in p.glob(f"{pattern}.png") if f.is_file()),
                key=lambda x: str(x).lower(),
            )
            yield from sorted(
                (f for f in p.glob(f"{pattern}.PNG") if f.is_file()),
                key=lambda x: str(x).lower(),
            )
        elif p.is_file() and p.suffix.lower() == ".png":
            yield p


def process_png(path_str: str, all_tags: bool, overwrite: bool) -> tuple[str, str, str]:
    png_path = Path(path_str)
    try:
        metadata = extract_png_text_metadata(png_path)
        md_path, wrote = write_markdown(
            png_path, metadata, all_tags=all_tags, overwrite=overwrite
        )
        if wrote:
            return (str(md_path), "wrote", "")
        return (str(md_path), "skipped", "")
    except Exception as exc:  # pragma: no cover
        return (str(png_path), "failed", str(exc))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract PNG metadata keys into Markdown sidecar files."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="PNG files or directories containing PNG files (default: current directory).",
    )
    parser.add_argument(
        "--all-tags",
        action="store_true",
        help="Write all discovered metadata tags instead of only parameters/postprocessing/extras.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Walk subdirectories when a directory path is provided.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes for PNG processing (default: 1).",
    )
    overwrite_group = parser.add_mutually_exclusive_group()
    overwrite_group.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing .md sidecar files (default behavior).",
    )
    overwrite_group.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip PNG files whose same-name .md file already exists.",
    )
    args = parser.parse_args()

    if args.workers < 1:
        print("--workers must be >= 1")
        return 1

    png_files = sorted(
        set(iter_png_files(args.paths, recursive=args.recursive)),
        key=lambda x: str(x).lower(),
    )
    if not png_files:
        print("No PNG files found.")
        return 1

    overwrite = not args.skip_existing
    failed_count = 0

    if args.workers == 1 or len(png_files) == 1:
        for png_path in png_files:
            md_or_png, status, error = process_png(
                str(png_path), args.all_tags, overwrite
            )
            if status == "wrote":
                print(f"Wrote: {md_or_png}")
            elif status == "skipped":
                print(f"Skipped: {md_or_png}")
            else:
                print(f"Failed: {md_or_png} ({error})")
                failed_count += 1
        return 1 if failed_count else 0

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(process_png, str(png_path), args.all_tags, overwrite): idx
            for idx, png_path in enumerate(png_files)
        }
        results: list[tuple[int, str, str, str]] = []
        for fut in as_completed(futures):
            idx = futures[fut]
            md_or_png, status, error = fut.result()
            results.append((idx, md_or_png, status, error))

        for _, md_or_png, status, error in sorted(results, key=lambda r: r[0]):
            if status == "wrote":
                print(f"Wrote: {md_or_png}")
            elif status == "skipped":
                print(f"Skipped: {md_or_png}")
            else:
                print(f"Failed: {md_or_png} ({error})")
                failed_count += 1

    return 1 if failed_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
