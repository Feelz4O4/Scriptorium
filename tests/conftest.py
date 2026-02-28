from __future__ import annotations

import struct
import subprocess
import sys
import zlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FOLIO_SCRIPT = REPO_ROOT / "Folio" / "folio.py"
OFFICINA_SCRIPT = REPO_ROOT / "Officina" / "officina.py"
VERSICLE_SCRIPT = REPO_ROOT / "Versicle" / "versicle.py"


def run_cli(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd or REPO_ROOT),
        text=True,
        capture_output=True,
    )


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    length = struct.pack(">I", len(data))
    crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    return length + chunk_type + data + crc


def write_minimal_png(path: Path, text_chunks: dict[str, str] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)  # 1x1 RGB
    scanline = b"\x00\x00\x00\x00"  # filter byte + one black pixel
    idat = zlib.compress(scanline)

    chunks: list[bytes] = [_png_chunk(b"IHDR", ihdr)]
    for key, value in (text_chunks or {}).items():
        payload = key.encode("latin-1") + b"\x00" + value.encode("latin-1")
        chunks.append(_png_chunk(b"tEXt", payload))
    chunks.extend([_png_chunk(b"IDAT", idat), _png_chunk(b"IEND", b"")])

    path.write_bytes(signature + b"".join(chunks))
    return path

