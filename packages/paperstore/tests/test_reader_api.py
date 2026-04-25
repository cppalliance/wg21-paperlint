#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Tests for paperstore's read surface: get_meta, get_source_path,
get_paper_md, list_mailing, put_source, and the ``from_uri`` factory.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from paperstore import (
    JsonBackend,
    MissingMailingIndexError,
    MissingMetaError,
    MissingPaperMdError,
    MissingSourceError,
    from_uri,
)


def test_put_source_then_get_source_path_roundtrip(tmp_path: Path):
    store = JsonBackend(tmp_path)
    path = store.put_source("p1234r0", b"%PDF-1.7\n", suffix=".pdf")
    assert path.name == "source.pdf"
    assert path.parent.name == "P1234R0"
    assert store.get_source_path("p1234r0") == path
    assert path.read_bytes() == b"%PDF-1.7\n"


def test_put_source_idempotent_for_identical_bytes(tmp_path: Path):
    store = JsonBackend(tmp_path)
    p1 = store.put_source("p1", b"aa", suffix=".pdf")
    mtime_before = p1.stat().st_mtime_ns
    p2 = store.put_source("p1", b"aa", suffix=".pdf")
    assert p1 == p2
    assert p2.stat().st_mtime_ns == mtime_before


def test_put_source_overwrites_differing_bytes(tmp_path: Path):
    store = JsonBackend(tmp_path)
    store.put_source("p1", b"v1", suffix=".pdf")
    store.put_source("p1", b"v2", suffix=".pdf")
    assert (tmp_path / "P1" / "source.pdf").read_bytes() == b"v2"


def test_put_source_rejects_missing_leading_dot(tmp_path: Path):
    store = JsonBackend(tmp_path)
    with pytest.raises(ValueError):
        store.put_source("p1", b"x", suffix="pdf")


def test_get_source_path_missing_raises(tmp_path: Path):
    store = JsonBackend(tmp_path)
    with pytest.raises(MissingSourceError):
        store.get_source_path("NOPE")


def test_get_source_path_rejects_multiple_sources(tmp_path: Path):
    store = JsonBackend(tmp_path)
    store.put_source("p1", b"pdf-bytes", suffix=".pdf")
    store.put_source("p1", b"<html></html>", suffix=".html")
    with pytest.raises(MissingSourceError, match="Multiple"):
        store.get_source_path("p1")


def test_get_meta_prefers_meta_json_over_mailing_row(tmp_path: Path):
    store = JsonBackend(tmp_path)
    store.upsert_mailing_index(
        "2026-02", [{"paper_id": "P1", "title": "from mailing"}]
    )
    store.write_meta_json("P1", {"title": "from meta.json"})
    assert store.get_meta("P1")["title"] == "from meta.json"


def test_get_meta_falls_back_to_mailing_row(tmp_path: Path):
    store = JsonBackend(tmp_path)
    store.upsert_mailing_index(
        "2026-02", [{"paper_id": "P1", "title": "only in mailing"}]
    )
    meta = store.get_meta("P1")
    assert meta["title"] == "only in mailing"
    assert meta["paper_id"] == "P1"


def test_get_meta_missing_raises(tmp_path: Path):
    store = JsonBackend(tmp_path)
    with pytest.raises(MissingMetaError):
        store.get_meta("P1")


def test_get_paper_md_roundtrip_and_missing(tmp_path: Path):
    store = JsonBackend(tmp_path)
    store.write_paper_md("P1", "# Hi\n")
    assert store.get_paper_md("p1") == "# Hi\n"
    with pytest.raises(MissingPaperMdError):
        store.get_paper_md("P2")


def test_list_mailing_roundtrip_and_missing(tmp_path: Path):
    store = JsonBackend(tmp_path)
    store.upsert_mailing_index("2026-02", [{"paper_id": "P1"}])
    rows = store.list_mailing("2026-02")
    assert [r["paper_id"] for r in rows] == ["P1"]
    with pytest.raises(MissingMailingIndexError):
        store.list_mailing("2099-12")


def test_from_uri_file_and_none(tmp_path: Path):
    b1 = from_uri(None, workspace_dir=tmp_path)
    assert isinstance(b1, JsonBackend)
    assert b1.workspace_dir == tmp_path

    b2 = from_uri(f"file://{tmp_path}")
    assert isinstance(b2, JsonBackend)
    assert b2.workspace_dir == tmp_path


def test_from_uri_rejects_unsupported_scheme(tmp_path: Path):
    with pytest.raises(ValueError, match="unsupported URI scheme"):
        from_uri("postgres://localhost/x", workspace_dir=tmp_path)
