from __future__ import annotations

import sys
from pathlib import Path

from conftest import FOLIO_SCRIPT, run_cli, write_minimal_png


def test_folio_basic_conversion_to_jpg(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    write_minimal_png(input_dir / "a.png")

    proc = run_cli(
        [
            sys.executable,
            str(FOLIO_SCRIPT),
            "--input",
            str(input_dir),
            "--output",
            str(output_dir),
        ]
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (output_dir / "a.jpg").exists()


def test_folio_skips_existing_without_overwrite(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    write_minimal_png(input_dir / "a.png")

    first = run_cli(
        [
            sys.executable,
            str(FOLIO_SCRIPT),
            "--input",
            str(input_dir),
            "--output",
            str(output_dir),
        ]
    )
    assert first.returncode == 0, first.stdout + first.stderr

    second = run_cli(
        [
            sys.executable,
            str(FOLIO_SCRIPT),
            "--input",
            str(input_dir),
            "--output",
            str(output_dir),
        ]
    )
    assert second.returncode == 0, second.stdout + second.stderr
    assert "Skipped" in second.stdout


def test_folio_recursive_finds_subdirectories(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    write_minimal_png(input_dir / "nested" / "a.png")

    proc = run_cli(
        [
            sys.executable,
            str(FOLIO_SCRIPT),
            "--input",
            str(input_dir),
            "--output",
            str(output_dir),
            "--recursive",
        ]
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (output_dir / "nested" / "a.jpg").exists()


def test_folio_invalid_input_exits_nonzero(tmp_path: Path):
    missing = tmp_path / "missing"
    proc = run_cli(
        [
            sys.executable,
            str(FOLIO_SCRIPT),
            "--input",
            str(missing),
        ]
    )
    assert proc.returncode != 0

