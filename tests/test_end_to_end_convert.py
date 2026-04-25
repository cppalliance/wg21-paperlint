#
# Copyright (c) 2026 Greg Kaleka (greg@gregkaleka.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""End-to-end: mailing.download -> tomd.api.convert -> paperstore artifacts.

Stubs ``requests.get`` so the test runs hermetically against a tomd fixture PDF.
This is the only cross-package test in the workspace; per-package suites cover
their own surfaces.
"""

from __future__ import annotations

from pathlib import Path

from mailing import download as mailing_download
from paperstore.testing import json_store  # noqa: F401  (re-exports pytest fixture)
from tomd.api import convert_paper


FIXTURE_PDF = (
    Path(__file__).resolve().parent.parent
    / "packages" / "tomd" / "tests" / "fixtures" / "golden" / "p1112r4.pdf"
)


class _FakeResp:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None


def test_end_to_end_convert(json_store, monkeypatch):
    paper_id = "P1112R4"
    mailing_id = "2026-04"
    pdf_bytes = FIXTURE_PDF.read_bytes()

    monkeypatch.setattr(
        mailing_download,
        "requests",
        type(
            "R",
            (),
            {"get": staticmethod(lambda url, timeout, headers: _FakeResp(pdf_bytes))},
        ),
    )

    json_store.upsert_mailing_index(
        mailing_id,
        [
            {
                "paper_id": paper_id,
                "title": "Test fixture paper",
                "authors": ["A. Author"],
                "subgroup": "EWG",
                "paper_type": "proposal",
            }
        ],
    )

    source_path = mailing_download.download_paper(
        paper_id,
        json_store,
        source_url="https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2026/p1112r4.pdf",
    )
    md = convert_paper(paper_id, json_store)

    workspace = json_store.workspace_dir
    assert source_path == workspace / paper_id / "source.pdf"
    assert source_path.is_file()
    assert source_path.read_bytes() == pdf_bytes

    assert (workspace / paper_id / "paper.md").is_file()
    assert (workspace / "mailings" / f"{mailing_id}.json").is_file()
    assert md.strip(), "convert_paper produced empty markdown"
