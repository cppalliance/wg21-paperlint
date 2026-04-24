#
# Copyright (c) 2026 Greg Kaleka (greg@gregkaleka.com)
#
# Distributed under the Boost Software License, Version 1.0.
#

"""Shape tests for the output-schema dataclasses in paperlint.models."""

from __future__ import annotations

import json
from dataclasses import asdict, fields

from paperlint.models import (
    SCHEMA_VERSION,
    Evaluation,
    FailureEntry,
    IndexPaperEntry,
    MailingIndex,
    OutputFinding,
    Paper,
    PaperMeta,
    Reference,
    RoomEntry,
    to_dict,
)


def _minimal_evaluation(**overrides) -> Evaluation:
    base = dict(
        schema_version=SCHEMA_VERSION,
        paperlint_sha="deadbeef0000",
        prompt_hash="cafef00d0000",
        source_url="https://example.org/P0000R0.html",
        pipeline_status="complete",
        paper="P0000R0",
        title="Example",
        authors=["Alice"],
        audience="LEWG",
        paper_type="proposal",
        generated="2026-04-23T00:00:00+00:00",
        model="anthropic/claude-opus-4.6",
        findings_discovered=0,
        findings_passed=0,
        findings_rejected=0,
        summary="No objective problems found.",
    )
    base.update(overrides)
    return Evaluation(**base)


def test_to_dict_evaluation_omits_unset_failure_fields() -> None:
    d = to_dict(_minimal_evaluation())
    for key in ("failure_stage", "failure_type", "failure_message", "failure_traceback"):
        assert key not in d, f"{key} should be absent when unset"


def test_to_dict_evaluation_includes_only_set_failure_fields() -> None:
    d = to_dict(
        _minimal_evaluation(
            pipeline_status="partial",
            failure_stage="analysis",
            failure_message="boom",
        )
    )
    assert d["failure_stage"] == "analysis"
    assert d["failure_message"] == "boom"
    assert "failure_type" not in d
    assert "failure_traceback" not in d


def test_to_dict_preserves_required_fields_with_empty_strings() -> None:
    # Empty strings are not None; they must survive the filter.
    d = to_dict(_minimal_evaluation(summary="", paper_type=""))
    assert d["summary"] == ""
    assert d["paper_type"] == ""


def test_to_dict_evaluation_field_names_match_design_doc() -> None:
    d = to_dict(_minimal_evaluation())
    expected = {
        "schema_version",
        "paperlint_sha",
        "prompt_hash",
        "source_url",
        "pipeline_status",
        "paper",
        "title",
        "authors",
        "audience",
        "paper_type",
        "generated",
        "model",
        "findings_discovered",
        "findings_passed",
        "findings_rejected",
        "summary",
        "findings",
        "references",
    }
    assert set(d.keys()) == expected


def test_reference_roundtrips_through_output_finding() -> None:
    ref = Reference(
        number=1,
        location="§5.2",
        quote="exact text",
        verified=True,
        extracted_char_start=120,
        extracted_char_end=131,
    )
    finding = OutputFinding(
        location="§5.2",
        description="defect desc",
        category="2.5",
        correction="should say …",
        references=[1],
    )
    ev = _minimal_evaluation(findings=[finding], references=[ref])
    payload = to_dict(ev)
    assert payload["references"][0] == {
        "number": 1,
        "location": "§5.2",
        "quote": "exact text",
        "verified": True,
        "extracted_char_start": 120,
        "extracted_char_end": 131,
    }
    assert payload["findings"][0]["references"] == [1]


def test_reference_without_char_offsets_omits_them() -> None:
    ref = Reference(number=1, location="§5.2", quote="x", verified=True)
    ev = _minimal_evaluation(references=[ref])
    ref_payload = to_dict(ev)["references"][0]
    assert "extracted_char_start" not in ref_payload
    assert "extracted_char_end" not in ref_payload


def test_paper_meta_from_dict_roundtrip() -> None:
    pm = PaperMeta(
        paper="P0000R0",
        title="Example",
        authors=["Alice", "Bob"],
        target_group="LEWG",
        paper_type="proposal",
        source_file="/tmp/P0000R0.html",
        run_timestamp="2026-04-23T00:00:00+00:00",
        model="anthropic/claude-opus-4.6",
    )
    roundtripped = PaperMeta.from_dict(asdict(pm))
    assert roundtripped == pm


def test_mailing_index_field_names_match_design_doc() -> None:
    idx = MailingIndex(
        schema_version=SCHEMA_VERSION,
        paperlint_sha="deadbeef0000",
        prompt_hash="cafef00d0000",
        mailing_id="2026-02",
        generated="2026-04-23T00:00:00+00:00",
        total_papers=1,
        succeeded=1,
        failed=0,
        partial=0,
        rooms={"LEWG": RoomEntry(papers=["P0000R0"], total_findings=3)},
        papers=[
            IndexPaperEntry(
                paper="P0000R0",
                title="Example",
                audience="LEWG",
                findings_passed=3,
                findings_discovered=5,
            )
        ],
    )
    d = to_dict(idx)
    expected = {
        "schema_version",
        "paperlint_sha",
        "prompt_hash",
        "mailing_id",
        "generated",
        "total_papers",
        "succeeded",
        "failed",
        "partial",
        "rooms",
        "papers",
    }
    assert set(d.keys()) == expected, (
        "failed_papers must be omitted when None, every other field must be present"
    )
    assert d["rooms"]["LEWG"] == {"papers": ["P0000R0"], "total_findings": 3}
    assert d["papers"][0]["paper"] == "P0000R0"


def test_mailing_index_includes_failed_papers_when_present() -> None:
    idx = MailingIndex(
        schema_version=SCHEMA_VERSION,
        paperlint_sha="x",
        prompt_hash="y",
        mailing_id="2026-02",
        generated="2026-04-23T00:00:00+00:00",
        total_papers=1,
        succeeded=0,
        failed=1,
        partial=0,
        failed_papers=[
            FailureEntry(paper="P0001R0", error="404 Not Found"),
        ],
    )
    d = to_dict(idx)
    assert d["failed_papers"] == [{"paper": "P0001R0", "error": "404 Not Found"}]


def test_failure_entry_omits_all_unset_fields() -> None:
    fe = FailureEntry(paper="P0001R0")
    assert to_dict(fe) == {"paper": "P0001R0"}


def test_to_dict_is_json_serializable() -> None:
    ev = _minimal_evaluation(
        findings=[
            OutputFinding(
                location="§5",
                description="x",
                category="1.1",
                correction="y",
                references=[1],
            )
        ],
        references=[Reference(number=1, location="§5", quote="z", verified=True)],
    )
    json.dumps(to_dict(ev))  # must not raise


def test_paper_matches_design_md_signature() -> None:
    """Pin Paper's field names, types, and order to design.md §4.

    If this test fails, the fix is usually to update design.md and this test
    together; drift between them defeats the point of §4.
    """
    expected = [
        ("document_id", str),
        ("mailing_id", str),
        ("title", str),
        ("authors", list[str]),
        ("mailing_date", str),
        ("publication_date", str),
        ("audience", list[str]),
        ("intent", str),
        ("url", str),
        ("markdown", str),
        ("meta_source", str),
    ]
    actual = [(f.name, f.type) for f in fields(Paper)]
    assert actual == expected


def test_paper_instantiates_with_all_fields() -> None:
    p = Paper(
        document_id="P3642R4",
        mailing_id="2026-02",
        title="Carry-less product: std::clmul",
        authors=["Jan Schultke"],
        mailing_date="2026-02-15",
        publication_date="2026-01-15",
        audience=["LEWG"],
        intent="ask",
        url="https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2026/p3642r4.html",
        markdown="# Carry-less product\n\n...",
        meta_source="mailing",
    )
    assert p.document_id == "P3642R4"
    assert p.audience == ["LEWG"]
    assert p.intent == "ask"
    assert p.meta_source == "mailing"
