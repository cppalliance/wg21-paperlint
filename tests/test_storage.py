#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Tests for the JSON storage backend.

Covers the on-disk layout described in ``paperlint.storage`` and the
idempotency contract for ``upsert_mailing_index``: re-running keeps each
existing entry (and its original ``added`` timestamp) and only appends
new papers.
"""

from __future__ import annotations

import json
from pathlib import Path

from paperlint.storage import JsonBackend


def test_layout_paper_md_meta_eval_intermediate(tmp_path: Path):
    backend = JsonBackend(tmp_path)

    backend.write_paper_md("p1234r0", "# Paper\n")
    backend.write_meta_json("p1234r0", {"title": "T"})
    backend.write_evaluation_json("p1234r0", {"summary": "S"})
    backend.write_intermediate("p1234r0", "1-findings", [{"n": 1}])

    paper_dir = tmp_path / "P1234R0"
    assert (paper_dir / "paper.md").read_text(encoding="utf-8") == "# Paper\n"
    assert json.loads((paper_dir / "meta.json").read_text())["title"] == "T"
    assert json.loads((paper_dir / "evaluation.json").read_text())["summary"] == "S"
    assert json.loads((paper_dir / "1-findings.json").read_text()) == [{"n": 1}]


def test_upsert_mailing_index_is_idempotent(tmp_path: Path):
    """Re-scraping the same mailing twice produces the same output bytes
    (no duplicate paper rows, no shifted ``added`` timestamps)."""
    backend = JsonBackend(tmp_path)

    papers = [
        {"paper_id": "p1234r0", "title": "Foo"},
        {"paper_id": "n5000", "title": "Bar"},
    ]
    merged_v1 = backend.upsert_mailing_index("2026-02", papers)
    bytes_v1 = backend.mailing_index_path("2026-02").read_bytes()

    merged_v2 = backend.upsert_mailing_index("2026-02", papers)
    bytes_v2 = backend.mailing_index_path("2026-02").read_bytes()

    assert merged_v1 == merged_v2
    assert bytes_v1 == bytes_v2
    assert [p["paper_id"] for p in merged_v2] == ["n5000", "p1234r0"]


def test_upsert_mailing_index_preserves_added_for_known_papers(tmp_path: Path):
    """When upstream re-publishes with extra papers, prior entries keep their
    original payload + ``added`` timestamp; new papers get a fresh one."""
    backend = JsonBackend(tmp_path)

    merged_v1 = backend.upsert_mailing_index(
        "2026-02",
        [{"paper_id": "p1234r0", "title": "Foo"}],
    )
    added_orig = {p["paper_id"]: p["added"] for p in merged_v1}

    merged_v2 = backend.upsert_mailing_index(
        "2026-02",
        [
            {"paper_id": "p1234r0", "title": "Foo updated upstream"},
            {"paper_id": "p9999r0", "title": "New paper"},
        ],
    )
    by_id = {p["paper_id"]: p for p in merged_v2}
    assert set(by_id) == {"p1234r0", "p9999r0"}
    assert by_id["p1234r0"]["title"] == "Foo"
    assert by_id["p1234r0"]["added"] == added_orig["p1234r0"]
    assert "added" in by_id["p9999r0"]


def test_mailing_index_path_under_workspace_dir(tmp_path: Path):
    backend = JsonBackend(tmp_path)
    p = backend.mailing_index_path("2026-02")
    assert p == tmp_path / "mailings" / "2026-02.json"
