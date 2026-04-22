#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Tests for the tomd-backed paperlint.extract wrapper.

Covers:
- Dispatch by file suffix to tomd's HTML / PDF converters.
- ``_apply_metadata_fallback`` injects only the fields that are missing
  from the markdown's YAML front matter.
- ``_strip_toc`` is still applied as a safety net.
- Empty markdown raises ``RuntimeError`` so the orchestrator's failure
  path records ``pipeline_status = "failed"``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from paperlint import extract


@pytest.fixture
def fake_html(tmp_path: Path) -> Path:
    p = tmp_path / "p1234r0.html"
    p.write_text("<html></html>", encoding="utf-8")
    return p


@pytest.fixture
def fake_pdf(tmp_path: Path) -> Path:
    p = tmp_path / "p5678r1.pdf"
    p.write_bytes(b"%PDF-1.4\n")
    return p


def _patch_html(monkeypatch, md: str, prompts: str | None = None):
    monkeypatch.setattr(extract, "convert_html", lambda _p: (md, prompts))


def _patch_pdf(monkeypatch, md: str, prompts: str | None = None):
    monkeypatch.setattr(extract, "convert_pdf", lambda _p: (md, prompts))


class TestExtractTextDispatch:
    def test_html_path_calls_convert_html(self, monkeypatch, fake_html):
        _patch_html(monkeypatch, "# Body\n\ntext\n")
        _patch_pdf(monkeypatch, "PDF SHOULD NOT BE CALLED", None)
        out = extract.extract_text(str(fake_html))
        assert "PDF SHOULD NOT BE CALLED" not in out
        assert "text" in out

    def test_pdf_path_calls_convert_pdf(self, monkeypatch, fake_pdf):
        _patch_html(monkeypatch, "HTML SHOULD NOT BE CALLED", None)
        _patch_pdf(monkeypatch, "# Body\n\ntext\n")
        out = extract.extract_text(str(fake_pdf))
        assert "HTML SHOULD NOT BE CALLED" not in out
        assert "text" in out


class TestEmptyMarkdownRaises:
    def test_empty_string_raises(self, monkeypatch, fake_pdf):
        _patch_pdf(monkeypatch, "", "# tomd - Slide Deck Detected\n")
        with pytest.raises(RuntimeError, match="empty markdown"):
            extract.extract_text(str(fake_pdf))

    def test_whitespace_only_raises(self, monkeypatch, fake_pdf):
        _patch_pdf(monkeypatch, "   \n\n\t\n", None)
        with pytest.raises(RuntimeError):
            extract.extract_text(str(fake_pdf))


class TestStripTocSafetyNet:
    def test_short_toc_block_is_stripped(self, monkeypatch, fake_html):
        body = (
            "# Paper\n\n"
            "## Contents\n"
            "1. Intro .... 1\n"
            "2. Body .... 2\n\n"
            "## Real Section\n\nText.\n"
        )
        _patch_html(monkeypatch, body)
        out = extract.extract_text(str(fake_html))
        assert "Real Section" in out
        assert "1. Intro" not in out


class TestMetadataFallback:
    def test_no_front_matter_inserts_block(self, monkeypatch, fake_html):
        _patch_html(monkeypatch, "Body only.\n")
        meta = {
            "title": "Carry-less product",
            "paper_id": "p3642r4",
            "subgroup": "LEWG",
            "authors": ["Alice <a@x>", "Bob <b@x>"],
            "document_date": "2026-02-15",
            "paper_type": "proposal",
        }
        out = extract.extract_text(str(fake_html), mailing_meta=meta)
        assert out.startswith("---\n")
        assert "title:" in out
        assert "Carry-less product" in out
        assert "document: p3642r4" in out
        assert "audience: LEWG" in out
        assert "reply-to:" in out
        assert "paper-type: proposal" in out
        assert "Body only." in out

    def test_existing_field_wins_over_fallback(self, monkeypatch, fake_html):
        body = (
            "---\n"
            'title: "Source Title"\n'
            "---\n\n"
            "Body.\n"
        )
        _patch_html(monkeypatch, body)
        meta = {"title": "Mailing Title", "subgroup": "LWG"}
        out = extract.extract_text(str(fake_html), mailing_meta=meta)
        assert '"Source Title"' in out
        assert "Mailing Title" not in out
        assert "audience: LWG" in out

    def test_empty_meta_value_skipped(self, monkeypatch, fake_html):
        _patch_html(monkeypatch, "Body.\n")
        meta = {"title": "T", "subgroup": "", "authors": [], "paper_id": None}
        out = extract.extract_text(str(fake_html), mailing_meta=meta)
        assert "title: T" in out
        assert "audience:" not in out
        assert "reply-to:" not in out
        assert "document:" not in out

    def test_no_meta_no_changes(self, monkeypatch, fake_html):
        _patch_html(monkeypatch, "Body only.\n")
        out = extract.extract_text(str(fake_html))
        assert "Body only." in out
        assert "---" not in out
