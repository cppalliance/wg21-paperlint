#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0.
#

"""Tests for failed pipeline paths: structured fields in ``evaluation.json`` and index ``failed_papers``."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import pytest

from paperlint import __main__ as paperlint_main
from paperlint.models import PaperMeta
from paperlint.orchestrator import run_paper_eval


def _write_converted(
    tmp_path: Path, paper_id: str, meta: PaperMeta, body: str = "paper body"
) -> None:
    d = tmp_path / paper_id.upper()
    d.mkdir(parents=True)
    (d / "paper.md").write_text(body, encoding="utf-8")
    (d / "meta.json").write_text(
        json.dumps(asdict(meta), ensure_ascii=False),
        encoding="utf-8",
    )


def test_run_paper_eval_missing_artifacts_raises(tmp_path: Path) -> None:
    mailing = {
        "title": "T",
        "authors": ["A"],
        "subgroup": "G",
    }
    with (
        patch("paperlint.orchestrator.ensure_api_keys"),
        patch("paperlint.orchestrator.build_client"),
        pytest.raises(FileNotFoundError),
    ):
        run_paper_eval(
            "N1234R0",
            workspace_dir=tmp_path,
            source_url="https://example.com/n1234r0.html",
            mailing_meta=mailing,
        )


def test_run_paper_eval_analysis_failure_writes_failure_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    meta = PaperMeta(
        paper="N1234R0",
        title="Title",
        authors=["A"],
        target_group="LEWG",
        paper_type="E",
        source_file="f",
        run_timestamp="2026-01-01T00:00:00+00:00",
        model="m",
    )
    _write_converted(tmp_path, "N1234R0", meta)
    monkeypatch.delenv("PAPERLINT_ERROR_TRACEBACK", raising=False)
    with (
        patch("paperlint.orchestrator.step_discovery", side_effect=RuntimeError("LLM timeout")),
        patch("paperlint.orchestrator.ensure_api_keys"),
        patch("paperlint.orchestrator.build_client"),
    ):
        out = run_paper_eval(
            "N1234R0",
            workspace_dir=tmp_path,
            source_url="https://example.com/n1234r0.html",
            mailing_meta={"title": "T", "authors": ["A"], "subgroup": "G"},
        )
    assert out.get("pipeline_status") == "partial"
    assert out.get("failure_stage") == "analysis"
    assert "timeout" in (out.get("failure_message") or "")


def test_run_paper_eval_includes_traceback_in_json_when_env_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    meta = PaperMeta(
        paper="N1234R0",
        title="Title",
        authors=[],
        target_group="G",
        paper_type="E",
        source_file="f",
        run_timestamp="2026-01-01T00:00:00+00:00",
        model="m",
    )
    _write_converted(tmp_path, "N1234R0", meta)
    monkeypatch.setenv("PAPERLINT_ERROR_TRACEBACK", "1")
    with (
        patch("paperlint.orchestrator.step_discovery", side_effect=RuntimeError("e")),
        patch("paperlint.orchestrator.ensure_api_keys"),
        patch("paperlint.orchestrator.build_client"),
    ):
        out = run_paper_eval(
            "N1234R0",
            workspace_dir=tmp_path,
            source_url="u",
            mailing_meta={"title": "T", "authors": [], "subgroup": "G"},
        )
    assert "failure_traceback" in out
    assert "RuntimeError" in out["failure_traceback"]


def test_failure_entry_includes_new_fields() -> None:
    r = {
        "paper": "P1R0",
        "status": "ok",
        "result": {
            "paper": "P1R0",
            "pipeline_status": "partial",
            "summary": "S",
            "failure_stage": "analysis",
            "failure_type": "OSError",
            "failure_message": "disk",
        },
    }
    e = paperlint_main._failure_entry(r)
    assert e.failure_message == "disk"
    assert e.failure_stage == "analysis"
    assert e.failure_type == "OSError"
