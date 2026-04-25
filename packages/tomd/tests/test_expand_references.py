#
# Copyright (c) 2026 Greg Kaleka (greg@gregkaleka.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Tests for ``tomd.__main__.expand_references``: mailing-id positional expansion."""

from __future__ import annotations

import pytest

from paperstore.errors import MissingMailingIndexError
from paperstore.testing import json_store  # noqa: F401  (pytest fixture)
from tomd.__main__ import expand_references


def _seed(json_store, mailing_id, paper_ids):
    json_store.upsert_mailing_index(
        mailing_id,
        [{"paper_id": pid, "url": f"https://x/{pid.lower()}.pdf"} for pid in paper_ids],
    )


def test_expand_paper_id_passthrough_uppercase(json_store):
    out = expand_references(["p3642r4", "P3700R0"], json_store)
    assert out == ["P3642R4", "P3700R0"]


def test_expand_mailing_id_emits_all_paper_ids(json_store):
    _seed(json_store, "2099-01", ["P1000R0", "P1001R0", "P1002R0"])
    out = expand_references(["2099-01"], json_store)
    assert out == ["P1000R0", "P1001R0", "P1002R0"]


def test_expand_mixed_inputs_preserve_order(json_store):
    _seed(json_store, "2099-01", ["P1000R0", "P1001R0"])
    out = expand_references(["P3642R4", "2099-01", "P3700R0"], json_store)
    assert out == ["P3642R4", "P1000R0", "P1001R0", "P3700R0"]


def test_expand_unknown_mailing_raises(json_store):
    with pytest.raises(MissingMailingIndexError):
        expand_references(["2099-12"], json_store)
