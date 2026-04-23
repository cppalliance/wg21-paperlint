"""Tests for the index-authoritative metadata contract.

Covers:
- _parse_eval_ref: the new <mailing-id>/<paper-id> CLI contract and its rejections.
- _infer_paper_type / normalize_paper_type: mailing index → ``info`` / ``ask`` only.

These are pure-function tests; no network, no LLM, no filesystem.
"""

import pytest

from paperlint.__main__ import _EVAL_CONTRACT_MSG, _parse_eval_ref
from paperlint.mailing import (
    _infer_paper_type,
    mailing_row_to_paper,
    normalize_paper_type,
    parse_audience_codes,
)


class TestParseEvalRef:
    def test_accepts_canonical(self):
        assert _parse_eval_ref("2026-02/P3642R4") == ("2026-02", "P3642R4")

    def test_uppercases_paper_id(self):
        assert _parse_eval_ref("2026-02/p3642r4") == ("2026-02", "P3642R4")

    def test_accepts_n_paper(self):
        assert _parse_eval_ref("2026-02/N5035") == ("2026-02", "N5035")

    def test_accepts_sd_paper(self):
        assert _parse_eval_ref("2026-02/SD-4") == ("2026-02", "SD-4")

    def test_rejects_bare_paper_id(self):
        with pytest.raises(ValueError) as exc:
            _parse_eval_ref("P3642R4")
        assert _EVAL_CONTRACT_MSG in str(exc.value)

    def test_rejects_local_path(self):
        with pytest.raises(ValueError):
            _parse_eval_ref("/tmp/paper.pdf")

    def test_rejects_relative_path(self):
        with pytest.raises(ValueError):
            _parse_eval_ref("./some/paper.pdf")

    def test_rejects_missing_paper(self):
        with pytest.raises(ValueError):
            _parse_eval_ref("2026-02/")

    def test_rejects_wrong_mailing_format(self):
        with pytest.raises(ValueError):
            _parse_eval_ref("2026/P3642R4")  # missing month
        with pytest.raises(ValueError):
            _parse_eval_ref("26-02/P3642R4")  # 2-digit year

    def test_whitespace_tolerated(self):
        assert _parse_eval_ref("  2026-02/P3642R4  ") == ("2026-02", "P3642R4")


class TestNormalizePaperType:
    def test_legacy_proposal(self):
        assert normalize_paper_type("proposal") == "ask"

    def test_legacy_informational(self):
        assert normalize_paper_type("informational") == "info"

    def test_legacy_white_paper(self):
        assert normalize_paper_type("white-paper") == "info"

    def test_none_defaults_ask(self):
        assert normalize_paper_type(None) == "ask"


class TestInferPaperType:
    def test_info_prefix_wins(self):
        assert _infer_paper_type("Info: Some Informational Topic", "P3999R0") == "info"

    def test_ask_prefix(self):
        assert _infer_paper_type("Ask: Should we do X?", "P3999R0") == "ask"

    def test_white_paper_pattern(self):
        t = "ISO/IEC JTC1/SC22/WG21 White Paper, Extensions to C++ for Transactional Memory"
        assert _infer_paper_type(t, "N5036") == "info"

    def test_n_paper_default_informational(self):
        assert _infer_paper_type("2026-03 WG21 admin telecon meeting", "N5035") == "info"

    def test_sd_maps_to_info(self):
        assert _infer_paper_type("WG21 Practices and Procedures", "SD-4") == "info"

    def test_p_paper_default_ask(self):
        assert _infer_paper_type("Carry-less product: std::clmul", "P3642R4") == "ask"

    def test_unknown_prefix_defaults_ask(self):
        assert _infer_paper_type("Some Title", "Q999") == "ask"

    def test_case_insensitive_paper_id(self):
        assert _infer_paper_type("admin", "n5035") == "info"
        assert _infer_paper_type("title", "p3642r4") == "ask"

    def test_info_prefix_beats_paper_id_letter(self):
        assert _infer_paper_type("Info: Design update", "P3999R0") == "info"

    def test_white_paper_beats_n_default(self):
        assert _infer_paper_type("WG21 White Paper on foo", "N5999") == "info"


class TestParseAudienceCodes:
    def test_multi_subgroup_string(self):
        s = "EWG Evolution,LEWG Library Evolution,CWG Core"
        assert parse_audience_codes(s) == ["EWG", "LEWG", "CWG"]

    def test_all_of_wg21(self):
        assert parse_audience_codes("All of WG21") == ["WG21"]

    def test_sg14(self):
        assert parse_audience_codes("SG14") == ["SG14"]

    def test_sg15_tooling(self):
        assert parse_audience_codes("SG15 Tooling,EWG Evolution") == ["SG15", "EWG"]


class TestMailingRowToPaper:
    def test_n5037_shape(self):
        row = {
            "paper_id": "n5037",
            "title": "March 2026 admin telecon",
            "authors": ["Guy Davidson"],
            "document_date": "2026-03-04",
            "subgroup": "All of WG21",
            "paper_type": "informational",
            "url": "https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2026/n5037.pdf",
        }
        p = mailing_row_to_paper(row, "2026-04", markdown="#x", meta_source="mailing")
        assert p.document_id == "N5037"
        assert p.mailing_id == "2026-04"
        assert p.intent == "info"
        assert p.audience == ["WG21"]
        assert p.markdown == "#x"
