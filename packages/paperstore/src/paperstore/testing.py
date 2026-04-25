#
# Copyright (c) 2026 Greg Kaleka (greg@gregkaleka.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Pytest fixtures for code that exercises a paperstore backend."""

from __future__ import annotations

import pytest

from paperstore import JsonBackend


@pytest.fixture
def json_store(tmp_path):
    """A fresh ``JsonBackend`` rooted at pytest's per-test ``tmp_path``."""
    return JsonBackend(tmp_path)
