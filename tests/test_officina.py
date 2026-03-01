from __future__ import annotations

import sys
from pathlib import Path

from conftest import OFFICINA_SCRIPT, run_cli, write_minimal_png


def _officina_base_args(input_dir: Path, output_dir: Path) -> list[str]:
    return [
        sys.executable,
        str(OFFICINA_SCRIPT),
        "--input",
        str(input_dir),
        "--output",
        str(output_dir),
        "--workers",
        "1",
    ]


def test_officina_basic_jpg_conversion(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    write_minimal_png(input_dir / "a.png")

    proc = run_cli(_officina_base_args(input_dir, output_dir))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (output_dir / "a.jpg").exists()


def test_officina_basic_webp_conversion(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    write_minimal_png(input_dir / "a.png")

    proc = run_cli(
        _officina_base_args(input_dir, output_dir) + ["--output-format", "webp"]
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (output_dir / "a.webp").exists()


def test_officina_skips_existing_without_overwrite(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    write_minimal_png(input_dir / "a.png")

    first = run_cli(_officina_base_args(input_dir, output_dir))
    assert first.returncode == 0, first.stdout + first.stderr

    second = run_cli(_officina_base_args(input_dir, output_dir))
    assert second.returncode == 0, second.stdout + second.stderr
    assert "Skipped" in second.stdout


def test_officina_recursive_mode_finds_subdirectories(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    write_minimal_png(input_dir / "nested" / "a.png")

    proc = run_cli(_officina_base_args(input_dir, output_dir))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (output_dir / "nested" / "a.jpg").exists()


def test_officina_non_recursive_ignores_subdirectories(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    write_minimal_png(input_dir / "nested" / "a.png")

    proc = run_cli(_officina_base_args(input_dir, output_dir) + ["--non-recursive"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not (output_dir / "nested" / "a.jpg").exists()
    assert "No matching files found." in proc.stdout


def test_officina_invalid_input_exits_nonzero(tmp_path: Path):
    missing = tmp_path / "missing"
    proc = run_cli(
        [
            sys.executable,
            str(OFFICINA_SCRIPT),
            "--input",
            str(missing),
        ]
    )
    assert proc.returncode != 0


def test_officina_max_size_mb_writes_under_limit(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    write_minimal_png(input_dir / "a.png")

    max_size_mb = 0.01  # 10KB
    proc = run_cli(
        _officina_base_args(input_dir, output_dir)
        + ["--max-size-mb", str(max_size_mb), "--min-quality", "20"]
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    out = output_dir / "a.jpg"
    assert out.exists()
    assert out.stat().st_size <= int(max_size_mb * 1024 * 1024)


def test_officina_dry_run_lists_without_writing_outputs(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    write_minimal_png(input_dir / "a.png")

    proc = run_cli(_officina_base_args(input_dir, output_dir) + ["--dry-run"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Would convert" in proc.stdout
    assert "Dry run done in" in proc.stdout
    assert not (output_dir / "a.jpg").exists()
