#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Tests for ``mailing.download.download_paper``.

``requests.get`` is monkeypatched so tests run hermetically.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mailing import download as md
from paperstore import JsonBackend


class _FakeResp:
    def __init__(self, content: bytes):
        self.content = content
        self.status_code = 200

    def raise_for_status(self) -> None:
        pass


def test_download_paper_stages_pdf_under_paperstore(tmp_path: Path, monkeypatch):
    pdf_bytes = b"%PDF-1.7\nhello"
    monkeypatch.setattr(md, "requests", type("R", (), {"get": lambda url, timeout, headers: _FakeResp(pdf_bytes)}))

    store = JsonBackend(tmp_path)
    path = md.download_paper(
        "p1234r0",
        store,
        source_url="https://www.open-std.org/.../p1234r0.pdf",
    )
    assert path == tmp_path / "P1234R0" / "source.pdf"
    assert path.read_bytes() == pdf_bytes
    assert store.get_source_path("p1234r0") == path


def test_download_paper_normalizes_htm_to_html(tmp_path: Path, monkeypatch):
    html_bytes = b"<html>ok</html>"
    monkeypatch.setattr(md, "requests", type("R", (), {"get": lambda url, timeout, headers: _FakeResp(html_bytes)}))

    store = JsonBackend(tmp_path)
    path = md.download_paper(
        "n5000",
        store,
        source_url="https://www.open-std.org/.../n5000.htm",
    )
    assert path == tmp_path / "N5000" / "source.html"


def test_download_paper_requires_source_url(tmp_path: Path):
    store = JsonBackend(tmp_path)
    with pytest.raises(ValueError, match="source_url"):
        md.download_paper("p1", store, source_url="")


def test_download_paper_rejects_unknown_suffix(tmp_path: Path):
    store = JsonBackend(tmp_path)
    with pytest.raises(ValueError, match="must end with"):
        md.download_paper("p1", store, source_url="https://x/paper.docx")
