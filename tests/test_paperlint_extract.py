#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Tests for the tomd-backed paperlint.extract wrapper.

Kept as ``test_paperlint_extract.py`` (not ``test_extract.py``) so collecting
both paperlint and vendored ``tomd/tests/`` in one pytest run does not collide
on the module name ``test_extract``.

Covers:
- Dispatch by file suffix to tomd's HTML / PDF converters (with provenance).
- ``_strip_toc`` is still applied as a safety net.
- Empty markdown raises ``RuntimeError`` so the orchestrator's failure
  path records ``pipeline_status = \"failed\"``.
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


def _patch_html(monkeypatch, md: str, prompts: str | None = None, prov=None):
    if prov is None:
        prov = {}
    monkeypatch.setattr(
        extract,
        "convert_html",
        lambda _p, mailing_meta=None: (md, prompts, prov),
    )


def _patch_pdf(monkeypatch, md: str, prompts: str | None = None, prov=None):
    if prov is None:
        prov = {}
    monkeypatch.setattr(
        extract,
        "convert_pdf",
        lambda _p, mailing_meta=None: (md, prompts, prov),
    )


class TestExtractTextDispatch:
    def test_html_path_calls_convert_html(self, monkeypatch, fake_html):
        _patch_html(monkeypatch, "# Body\n\ntext\n")
        _patch_pdf(monkeypatch, "PDF SHOULD NOT BE CALLED", None)
        md, prov = extract.extract_text(str(fake_html))
        assert "PDF SHOULD NOT BE CALLED" not in md
        assert "text" in md
        assert isinstance(prov, dict)

    def test_pdf_path_calls_convert_pdf(self, monkeypatch, fake_pdf):
        _patch_html(monkeypatch, "HTML SHOULD NOT BE CALLED", None)
        _patch_pdf(monkeypatch, "# Body\n\ntext\n")
        md, prov = extract.extract_text(str(fake_pdf))
        assert "HTML SHOULD NOT BE CALLED" not in md
        assert "text" in md
        assert isinstance(prov, dict)


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
        md, _ = extract.extract_text(str(fake_html))
        assert "Real Section" in md
        assert "1. Intro" not in md


class TestExtractReturnsProvenance:
    def test_provenance_passed_through(self, monkeypatch, fake_html):
        _patch_html(monkeypatch, "ok\n", None, {"title": "mailing", "document": "tomd"})
        md, prov = extract.extract_text(str(fake_html), mailing_meta={"x": 1})
        assert md.strip() == "ok"
        assert prov["title"] == "mailing"


class TestNoMeta:
    def test_no_meta_no_changes(self, monkeypatch, fake_html):
        _patch_html(monkeypatch, "Body only.\n")
        md, prov = extract.extract_text(str(fake_html))
        assert "Body only." in md
        assert "---" not in md
        assert prov == {}
