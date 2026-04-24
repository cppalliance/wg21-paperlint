#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Tests for ``tomd.api.convert_paper`` and the YAML-fallback helpers.

Named ``test_paper_extract`` to avoid collision with ``tomd/tests/test_extract.py``
(which covers spatial PDF extraction).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from paperstore import JsonBackend, MissingMetaError, MissingSourceError
from tomd import api


def _stage(store: JsonBackend, paper_id: str, *, suffix: str, mailing_row: dict) -> None:
    """Populate paperstore with a minimal source file + mailing-index row."""
    store.put_source(paper_id, b"ignored-by-monkeypatched-converter", suffix=suffix)
    row = {"paper_id": paper_id.lower(), **mailing_row}
    store.upsert_mailing_index("2026-02", [row])


def _patch_html(monkeypatch, md: str, prompts: str | None = None):
    monkeypatch.setattr(api, "convert_html", lambda _p: (md, prompts))


def _patch_pdf(monkeypatch, md: str, prompts: str | None = None):
    monkeypatch.setattr(api, "convert_pdf", lambda _p: (md, prompts))


class TestDispatch:
    def test_html_path_calls_convert_html(self, tmp_path: Path, monkeypatch):
        store = JsonBackend(tmp_path)
        _stage(store, "P1", suffix=".html", mailing_row={"title": "T"})
        _patch_html(monkeypatch, "# Body\n\ntext\n")
        _patch_pdf(monkeypatch, "PDF SHOULD NOT BE CALLED")
        out = api.convert_paper("P1", store)
        assert "PDF SHOULD NOT BE CALLED" not in out
        assert "text" in out
        assert store.get_paper_md("P1") == out

    def test_pdf_path_calls_convert_pdf(self, tmp_path: Path, monkeypatch):
        store = JsonBackend(tmp_path)
        _stage(store, "P1", suffix=".pdf", mailing_row={"title": "T"})
        _patch_html(monkeypatch, "HTML SHOULD NOT BE CALLED")
        _patch_pdf(monkeypatch, "# Body\n\ntext\n")
        out = api.convert_paper("P1", store)
        assert "HTML SHOULD NOT BE CALLED" not in out
        assert "text" in out


class TestEmptyMarkdownRaises:
    def test_empty_string_raises(self, tmp_path: Path, monkeypatch):
        store = JsonBackend(tmp_path)
        _stage(store, "P1", suffix=".pdf", mailing_row={"title": "T"})
        _patch_pdf(monkeypatch, "", "# tomd - Slide Deck Detected\n")
        with pytest.raises(RuntimeError, match="empty markdown"):
            api.convert_paper("P1", store)

    def test_whitespace_only_raises(self, tmp_path: Path, monkeypatch):
        store = JsonBackend(tmp_path)
        _stage(store, "P1", suffix=".pdf", mailing_row={"title": "T"})
        _patch_pdf(monkeypatch, "   \n\n\t\n")
        with pytest.raises(RuntimeError):
            api.convert_paper("P1", store)


class TestStripTocSafetyNet:
    def test_short_toc_block_is_stripped(self, tmp_path: Path, monkeypatch):
        store = JsonBackend(tmp_path)
        _stage(store, "P1", suffix=".html", mailing_row={"title": "T"})
        body = (
            "# Paper\n\n"
            "## Contents\n"
            "1. Intro .... 1\n"
            "2. Body .... 2\n\n"
            "## Real Section\n\nText.\n"
        )
        _patch_html(monkeypatch, body)
        out = api.convert_paper("P1", store)
        assert "Real Section" in out
        assert "1. Intro" not in out


class TestMetadataFallback:
    def test_no_front_matter_inserts_block(self, tmp_path: Path, monkeypatch):
        store = JsonBackend(tmp_path)
        _stage(
            store, "P3642R4", suffix=".html",
            mailing_row={
                "title": "Carry-less product",
                "subgroup": "LEWG",
                "authors": ["Alice <a@x>", "Bob <b@x>"],
                "document_date": "2026-02-15",
                "paper_type": "proposal",
            },
        )
        _patch_html(monkeypatch, "Body only.\n")
        out = api.convert_paper("P3642R4", store)
        assert out.startswith("---\n")
        assert "title:" in out
        assert "Carry-less product" in out
        assert "document: p3642r4" in out
        assert "audience: LEWG" in out
        assert "reply-to:" in out
        assert "paper-type: proposal" in out
        assert "Body only." in out

    def test_existing_field_wins_over_fallback(self, tmp_path: Path, monkeypatch):
        store = JsonBackend(tmp_path)
        _stage(
            store, "P1", suffix=".html",
            mailing_row={"title": "Mailing Title", "subgroup": "LWG"},
        )
        body = (
            "---\n"
            'title: "Source Title"\n'
            "---\n\n"
            "Body.\n"
        )
        _patch_html(monkeypatch, body)
        out = api.convert_paper("P1", store)
        assert '"Source Title"' in out
        assert "Mailing Title" not in out
        assert "audience: LWG" in out

    def test_empty_meta_value_skipped(self, tmp_path: Path, monkeypatch):
        store = JsonBackend(tmp_path)
        _stage(
            store, "P1", suffix=".html",
            mailing_row={"title": "T", "subgroup": "", "authors": []},
        )
        _patch_html(monkeypatch, "Body.\n")
        out = api.convert_paper("P1", store)
        assert "title: T" in out
        assert "audience:" not in out
        assert "reply-to:" not in out


class TestErrors:
    def test_missing_source_raises(self, tmp_path: Path):
        store = JsonBackend(tmp_path)
        store.upsert_mailing_index(
            "2026-02", [{"paper_id": "p1", "title": "T"}]
        )
        with pytest.raises(MissingSourceError):
            api.convert_paper("P1", store)

    def test_missing_meta_raises(self, tmp_path: Path):
        store = JsonBackend(tmp_path)
        store.put_source("P1", b"x", suffix=".pdf")
        with pytest.raises(MissingMetaError):
            api.convert_paper("P1", store)
