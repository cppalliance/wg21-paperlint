#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Transition shim: scrape/download live in the ``mailing`` package now.

``fetch_paper`` remains here for one more PR: ``paperlint.orchestrator``
still calls it against a cache directory. PR3 rewires the orchestrator to
``mailing.download.download_paper`` through a paperstore instance, at
which point this module is deleted.
"""

from __future__ import annotations

import logging
from pathlib import Path

import requests

from mailing.scrape import (
    _infer_paper_type,
    fetch_mailing_paper_ids,
    fetch_papers_for_mailing,
    parse_papers_for_mailing,
)

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT_SEC = 120

__all__ = [
    "_infer_paper_type",
    "fetch_mailing_paper_ids",
    "fetch_paper",
    "fetch_papers_for_mailing",
    "parse_papers_for_mailing",
]


def fetch_paper(paper_id: str, cache_dir: Path | None = None, source_url: str = "") -> Path:
    """Legacy downloader using ``.paperlint_cache/``. Deleted in PR3."""
    if not source_url:
        raise ValueError(
            f"fetch_paper requires source_url (authoritative from mailing index). "
            f"Paper: {paper_id}."
        )
    if cache_dir is None:
        cache_dir = Path.cwd() / ".paperlint_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    filename = source_url.rsplit("/", 1)[-1].lower()
    local = cache_dir / filename
    if local.exists():
        logger.info("Found cached: %s", local)
        return local
    logger.info("Downloading: %s", source_url)
    resp = requests.get(source_url, timeout=_FETCH_TIMEOUT_SEC, stream=True)
    resp.raise_for_status()
    local.write_bytes(resp.content)
    logger.info("Downloaded: %s", local)
    return local
