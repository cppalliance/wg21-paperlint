#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0.
#

from __future__ import annotations

from paperlint import __main__ as m


def test_merge_paper_selectors_single() -> None:
    assert m._merge_paper_selectors("P1R0", None) == "P1R0"


def test_merge_paper_selectors_comma_only() -> None:
    assert m._merge_paper_selectors(None, "A, B") == "A,B"


def test_merge_paper_selectors_both() -> None:
    assert m._merge_paper_selectors("X", "Y,Z") == "X,Y,Z"
