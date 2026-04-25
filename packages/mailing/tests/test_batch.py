#
# Copyright (c) 2026 Greg Kaleka (greg@gregkaleka.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Tests for ``mailing.batch.stage_mailing``: idempotent corpus staging."""

from __future__ import annotations

from pathlib import Path

from mailing.batch import stage_mailing
from paperstore.testing import json_store  # noqa: F401  (pytest fixture)


def _rows(*paper_ids: str) -> list[dict]:
    return [
        {
            "paper_id": pid,
            "url": f"https://www.open-std.org/.../{pid.lower()}.pdf",
            "filename": f"{pid.lower()}.pdf",
            "title": f"Paper {pid}",
            "authors": [],
            "subgroup": "EWG",
            "paper_type": "proposal",
        }
        for pid in paper_ids
    ]


def test_stage_mailing_first_run_downloads_all(json_store):
    rows = _rows("P1000R0", "P1001R0")
    download_calls: list[str] = []

    def fake_download(pid, store, *, source_url):
        download_calls.append(pid)
        return store.put_source(pid, b"%PDF-1.7\n", suffix=".pdf")

    counts = stage_mailing(
        "2099-01",
        json_store,
        fetch_papers=lambda mid: rows,
        download=fake_download,
    )

    assert counts == {
        "papers_in_index": 2,
        "downloaded": 2,
        "skipped": 0,
        "no_url": 0,
        "filtered_out": 0,
    }
    assert sorted(download_calls) == ["P1000R0", "P1001R0"]


def test_stage_mailing_second_run_is_a_noop(json_store):
    rows = _rows("P1000R0", "P1001R0")
    download_calls: list[str] = []

    def fake_download(pid, store, *, source_url):
        download_calls.append(pid)
        return store.put_source(pid, b"%PDF-1.7\n", suffix=".pdf")

    stage_mailing(
        "2099-01",
        json_store,
        fetch_papers=lambda mid: rows,
        download=fake_download,
    )
    assert len(download_calls) == 2

    counts = stage_mailing(
        "2099-01",
        json_store,
        fetch_papers=lambda mid: rows,
        download=fake_download,
    )

    assert counts["downloaded"] == 0
    assert counts["skipped"] == 2
    assert len(download_calls) == 2  # no extra calls


def test_stage_mailing_picks_up_new_papers_only(json_store):
    download_calls: list[str] = []

    def fake_download(pid, store, *, source_url):
        download_calls.append(pid)
        return store.put_source(pid, b"%PDF-1.7\n", suffix=".pdf")

    stage_mailing(
        "2099-01",
        json_store,
        fetch_papers=lambda mid: _rows("P1000R0"),
        download=fake_download,
    )
    assert download_calls == ["P1000R0"]

    counts = stage_mailing(
        "2099-01",
        json_store,
        fetch_papers=lambda mid: _rows("P1000R0", "P1001R0"),
        download=fake_download,
    )

    assert counts["downloaded"] == 1
    assert counts["skipped"] == 1
    assert download_calls == ["P1000R0", "P1001R0"]


def test_stage_mailing_refetch_redownloads_all(json_store):
    rows = _rows("P1000R0", "P1001R0")
    download_calls: list[str] = []

    def fake_download(pid, store, *, source_url):
        download_calls.append(pid)
        return store.put_source(pid, b"%PDF-1.7\n", suffix=".pdf")

    stage_mailing(
        "2099-01", json_store,
        fetch_papers=lambda mid: rows, download=fake_download,
    )
    counts = stage_mailing(
        "2099-01", json_store, refetch=True,
        fetch_papers=lambda mid: rows, download=fake_download,
    )

    assert counts["downloaded"] == 2
    assert counts["skipped"] == 0
    assert len(download_calls) == 4  # two per run


def test_stage_mailing_filter_subset(json_store):
    rows = _rows("P1000R0", "P1001R0", "P1002R0")
    download_calls: list[str] = []

    def fake_download(pid, store, *, source_url):
        download_calls.append(pid)
        return store.put_source(pid, b"%PDF-1.7\n", suffix=".pdf")

    counts = stage_mailing(
        "2099-01", json_store,
        papers={"P1001R0"},
        fetch_papers=lambda mid: rows, download=fake_download,
    )

    assert counts["downloaded"] == 1
    assert counts["filtered_out"] == 2
    assert download_calls == ["P1001R0"]


def test_stage_mailing_no_papers_in_mailing(json_store):
    counts = stage_mailing(
        "2099-01", json_store,
        fetch_papers=lambda mid: [],
        download=lambda *a, **kw: Path("/dev/null"),
    )
    assert counts == {
        "papers_in_index": 0,
        "downloaded": 0,
        "skipped": 0,
        "no_url": 0,
        "filtered_out": 0,
    }


def test_stage_mailing_row_without_url(json_store):
    rows = [
        {
            "paper_id": "P1000R0",
            "url": "",
            "filename": "p1000r0.pdf",
            "title": "no url",
            "authors": [],
            "subgroup": "EWG",
            "paper_type": "proposal",
        }
    ]
    download_calls: list[str] = []

    def fake_download(pid, store, *, source_url):
        download_calls.append(pid)
        return store.put_source(pid, b"x", suffix=".pdf")

    counts = stage_mailing(
        "2099-01", json_store,
        fetch_papers=lambda mid: rows, download=fake_download,
    )

    assert counts["no_url"] == 1
    assert counts["downloaded"] == 0
    assert download_calls == []
