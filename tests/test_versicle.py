from __future__ import annotations

import sys
from pathlib import Path

from conftest import VERSICLE_SCRIPT, run_cli, write_minimal_png


def test_versicle_parameters_chunk_writes_markdown(tmp_path: Path):
    png = write_minimal_png(tmp_path / "a.png", {"parameters": "prompt text"})

    proc = run_cli([sys.executable, str(VERSICLE_SCRIPT), str(png)])
    assert proc.returncode == 0, proc.stdout + proc.stderr

    md = png.with_suffix(".md")
    assert md.exists()
    text = md.read_text(encoding="utf-8")
    assert "## parameters" in text
    assert "prompt text" in text


def test_versicle_skip_existing_does_not_overwrite(tmp_path: Path):
    png = write_minimal_png(tmp_path / "a.png", {"parameters": "new value"})
    md = png.with_suffix(".md")
    md.write_text("sentinel\n", encoding="utf-8")

    proc = run_cli(
        [sys.executable, str(VERSICLE_SCRIPT), str(png), "--skip-existing"]
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Skipped:" in proc.stdout
    assert md.read_text(encoding="utf-8") == "sentinel\n"


def test_versicle_all_tags_includes_extra_keys(tmp_path: Path):
    png = write_minimal_png(
        tmp_path / "a.png",
        {"parameters": "p", "extras": "e", "custom": "c"},
    )

    proc = run_cli([sys.executable, str(VERSICLE_SCRIPT), str(png), "--all-tags"])
    assert proc.returncode == 0, proc.stdout + proc.stderr

    text = png.with_suffix(".md").read_text(encoding="utf-8")
    assert "## custom" in text
    assert "## parameters" in text
    assert "## extras" in text


def test_versicle_invalid_png_fails_gracefully(tmp_path: Path):
    bad = tmp_path / "bad.png"
    bad.write_text("not a png", encoding="utf-8")

    proc = run_cli([sys.executable, str(VERSICLE_SCRIPT), str(bad)])
    assert proc.returncode != 0
    assert "Failed:" in proc.stdout

