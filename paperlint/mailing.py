#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Transition shim: scrape lives in the ``mailing`` package now.

Deleted in PR4 once all paperlint-internal imports reference
``mailing.scrape`` directly.
"""

from __future__ import annotations

from mailing.scrape import (
    _infer_paper_type,
    fetch_mailing_paper_ids,
    fetch_papers_for_mailing,
    parse_papers_for_mailing,
)

__all__ = [
    "_infer_paper_type",
    "fetch_mailing_paper_ids",
    "fetch_papers_for_mailing",
    "parse_papers_for_mailing",
]
