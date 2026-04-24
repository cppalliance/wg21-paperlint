#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""WG21 mailing index scraper + paper-source downloader."""

from __future__ import annotations

from mailing.download import download_paper
from mailing.scrape import (
    fetch_mailing_paper_ids,
    fetch_papers_for_mailing,
    parse_papers_for_mailing,
)

__all__ = [
    "download_paper",
    "fetch_mailing_paper_ids",
    "fetch_papers_for_mailing",
    "parse_papers_for_mailing",
]
