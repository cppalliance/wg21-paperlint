"""Smoke tests for the tomd CLI entry point.

The new CLI takes a paper id and a paperstore workspace; the old file-path
interface (``tomd input.pdf``) was removed in the 0.2 restructure.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from paperstore import JsonBackend


def test_tomd_help_succeeds():
    result = subprocess.run(
        [sys.executable, "-m", "tomd", "--help"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "paper" in result.stdout.lower()


def test_tomd_missing_source_errors(tmp_path: Path):
    store = JsonBackend(tmp_path)
    store.upsert_mailing_index(
        "2026-02", [{"paper_id": "P1", "title": "T", "paper_type": "proposal"}]
    )
    result = subprocess.run(
        [sys.executable, "-m", "tomd", "P1", "--workspace-dir", str(tmp_path)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0
    assert "source" in result.stderr.lower()
