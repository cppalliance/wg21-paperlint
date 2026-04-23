"""Tests for mailing-index merge into YAML metadata (mailing wins per key)."""

from __future__ import annotations

from lib import format_front_matter
from lib.mailing_merge import (
    FRONT_MATTER_KEYS,
    merge_yaml_with_mailing,
    rollup_meta_source,
)


def test_merge_mailing_wins_title_over_source():
    source = {"title": "Source Title", "document": "P1R0", "date": "2020-01-01"}
    mailing = {
        "title": "Mailing Title",
        "paper_id": "p3642r4",
        "document_date": "2026-02-15",
        "subgroup": "LEWG",
        "authors": ["Alice"],
        "paper_type": "ask",
    }
    merged, prov = merge_yaml_with_mailing(source, mailing)
    assert merged["title"] == "Mailing Title"
    assert prov["title"] == "mailing"
    assert merged["document"] == "P3642R4"
    assert prov["document"] == "mailing"


def test_merge_source_fallback_when_mailing_missing_title():
    source = {"title": "Only Source", "document": "P1R0"}
    mailing = {
        "title": "",
        "paper_id": "p1r0",
        "document_date": "2026-01-01",
        "subgroup": "EWG",
        "authors": ["A"],
        "paper_type": "ask",
    }
    merged, prov = merge_yaml_with_mailing(source, mailing)
    assert merged["title"] == "Only Source"
    assert prov["title"] == "tomd"


def test_front_matter_key_order():
    merged = {
        "title": "T",
        "document": "P1R0",
        "date": "2026-01-01",
        "intent": "ask",
        "audience": ["LEWG"],
        "reply-to": ["A"],
    }
    fm = format_front_matter(merged)
    ti = fm.index("title:")
    di = fm.index("document:")
    dti = fm.index("date:")
    ii = fm.index("intent:")
    ai = fm.index("audience:")
    ri = fm.index("reply-to:")
    assert ti < di < dti < ii < ai < ri


def test_rollup_all_mailing():
    prov = {k: "mailing" for k in FRONT_MATTER_KEYS}
    assert rollup_meta_source(prov) == "mailing"


def test_rollup_mixed():
    prov = {
        "title": "mailing",
        "document": "mailing",
        "date": "mailing",
        "intent": "mailing",
        "audience": "mailing",
        "reply-to": "tomd",
    }
    assert rollup_meta_source(prov) == "merged"
