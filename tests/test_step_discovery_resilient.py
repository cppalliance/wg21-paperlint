#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0.
#

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from paperlint.models import Evidence, Finding, PaperMeta
from paperlint.pipeline import step_discovery


def _find(n: int) -> Finding:
    return Finding(
        number=n,
        title="t",
        category="1.1",
        defect="d",
        correction="c",
        axiom="a",
        evidence=[Evidence(location="L", quote="q")],
    )


@pytest.mark.parametrize("passes", [2, 3])
def test_step_discovery_pass_fails_later_pass_can_succeed(passes: int) -> None:
    client = MagicMock()
    meta = PaperMeta(
        paper="P",
        title="T",
        authors=[],
        target_group="G",
        paper_type="E",
        source_file="f",
        run_timestamp="2020-01-01T00:00:00+00:00",
        model="m",
    )
    call_n = 0

    def fake_run(*_a, **_k):
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            raise RuntimeError("transient")
        return [_find(1)]

    with patch("paperlint.pipeline._run_discovery_call", side_effect=fake_run):
        out = step_discovery(client, "text", meta, passes=passes)
    assert len(out) == 1
    assert out[0].title == "t"


def test_step_discovery_all_passes_fail_raises() -> None:
    client = MagicMock()
    meta = PaperMeta(
        paper="P",
        title="T",
        authors=[],
        target_group="G",
        paper_type="E",
        source_file="f",
        run_timestamp="2020-01-01T00:00:00+00:00",
        model="m",
    )
    with (
        patch(
            "paperlint.pipeline._run_discovery_call",
            side_effect=RuntimeError("all bad"),
        ),
        pytest.raises(RuntimeError, match="all bad"),
    ):
        step_discovery(client, "x", meta, passes=2)
