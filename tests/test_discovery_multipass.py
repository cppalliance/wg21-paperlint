#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Unit tests for multi-pass step_discovery (fake LLM client, no network)."""

from __future__ import annotations

import json

import pytest

from paperlint.models import PaperMeta
from paperlint.pipeline import step_discovery


def _meta() -> PaperMeta:
    return PaperMeta(
        paper="P1",
        title="Test Title",
        authors=["Alice"],
        target_group="LEWG",
        paper_type="proposal",
        source_file="/tmp/p1.html",
        run_timestamp="2026-01-01T00:00:00+00:00",
        model="test-model",
    )


class _FakeUsage:
    prompt_tokens = 1
    completion_tokens = 1
    total_tokens = 2


def _fake_response(content: str):
    class _Msg:
        def __init__(self, c: str) -> None:
            self.content = c

    class _Choice:
        def __init__(self, c: str) -> None:
            self.message = _Msg(c)

    class _R:
        def __init__(self, c: str) -> None:
            self.choices = [_Choice(c)]
            self.usage = _FakeUsage()

    return _R(content)


class FakeClient:
    """OpenAI-shaped client: ``chat.completions.create`` returns canned JSON."""

    class _Completions:
        def __init__(self, outer: FakeClient) -> None:
            self._outer = outer

        def create(self, **kwargs):
            self._outer.api_calls.append(kwargs)
            obj = self._outer._payloads[self._outer._i]
            self._outer._i += 1
            return _fake_response(json.dumps(obj))

    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = payloads
        self._i = 0
        self.api_calls: list[dict] = []
        self.chat = type("_Chat", (), {"completions": self._Completions(self)})()


def test_single_pass_renumbers_and_one_llm_call():
    payload = {
        "findings": [
            {
                "number": 99,
                "title": "One defect",
                "category": "1.1",
                "defect": "d",
                "correction": "c",
                "axiom": "a",
                "evidence": [{"location": "§1", "quote": "verbatim"}],
            }
        ]
    }
    client = FakeClient([payload])
    out = step_discovery(client, "paper body", _meta(), passes=1)
    assert len(out) == 1
    assert out[0].number == 1
    assert out[0].title == "One defect"
    assert len(client.api_calls) == 1


def test_two_passes_appends_new_and_dedupes():
    p1 = {
        "findings": [
            {
                "number": 1,
                "title": "A",
                "category": "1.1",
                "defect": "d",
                "correction": "c",
                "axiom": "a",
                "evidence": [{"location": "L1", "quote": "q1"}],
            },
            {
                "number": 2,
                "title": "B",
                "category": "1.2",
                "defect": "d",
                "correction": "c",
                "axiom": "a",
                "evidence": [{"location": "L2", "quote": "q2"}],
            },
        ]
    }
    p2 = {
        "findings": [
            {
                "number": 1,
                "title": "A dup",
                "category": "1.1",
                "defect": "other",
                "correction": "c",
                "axiom": "a",
                "evidence": [{"location": "L1", "quote": "q1"}],
            },
            {
                "number": 2,
                "title": "C",
                "category": "2.0",
                "defect": "d",
                "correction": "c",
                "axiom": "a",
                "evidence": [{"location": "L3", "quote": "q3"}],
            },
            {
                "number": 3,
                "title": "D",
                "category": "2.1",
                "defect": "d",
                "correction": "c",
                "axiom": "a",
                "evidence": [{"location": "L4", "quote": "q4"}],
            },
        ]
    }
    client = FakeClient([p1, p2])
    out = step_discovery(client, "body", _meta(), passes=2)
    assert len(out) == 4
    assert [f.number for f in out] == [1, 2, 3, 4]
    assert [f.title for f in out] == ["A", "B", "C", "D"]


def test_dedup_normalizes_whitespace_and_case_in_quote_and_location():
    p1 = {
        "findings": [
            {
                "number": 1,
                "title": "First",
                "category": "3.0",
                "defect": "d",
                "correction": "c",
                "axiom": "a",
                "evidence": [{"location": "Sec A", "quote": "The quick brown"}],
            }
        ]
    }
    p2 = {
        "findings": [
            {
                "number": 1,
                "title": "Same again",
                "category": "3.0",
                "defect": "d2",
                "correction": "c",
                "axiom": "a",
                "evidence": [{"location": "sec a", "quote": "  THE  quick   brown"}],
            },
            {
                "number": 2,
                "title": "Truly new",
                "category": "3.1",
                "defect": "d",
                "correction": "c",
                "axiom": "a",
                "evidence": [{"location": "L99", "quote": "unique"}],
            },
        ]
    }
    client = FakeClient([p1, p2])
    out = step_discovery(client, "x", _meta(), passes=2)
    assert len(out) == 2
    assert out[0].title == "First"
    assert out[1].title == "Truly new"


def test_pass_2_user_message_contains_prior_findings_block():
    p1 = {
        "findings": [
            {
                "number": 1,
                "title": "Alpha defect",
                "category": "1.0",
                "defect": "d",
                "correction": "c",
                "axiom": "a",
                "evidence": [{"location": "§9", "quote": "snippet from paper"}],
            }
        ]
    }
    p2 = {"findings": []}
    client = FakeClient([p1, p2])
    step_discovery(client, "paper markdown", _meta(), passes=2)
    assert len(client.api_calls) == 2
    user2 = client.api_calls[1]["messages"][1]["content"]
    assert "Previously Found Defects" in user2
    assert "Alpha defect" in user2
    assert "snippet from paper" in user2


def test_passes_must_be_at_least_one():
    client = FakeClient([{"findings": []}])
    with pytest.raises(ValueError, match="passes must be"):
        step_discovery(client, "x", _meta(), passes=0)
