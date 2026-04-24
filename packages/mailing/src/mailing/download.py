#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Download staged paper sources into a paperstore-backed workspace."""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlparse

import requests

from paperstore.backend import StorageBackend

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT_SEC = 120
_USER_AGENT = "paperflow/0.1 (+https://github.com/cppalliance/paperlint)"
_ALLOWED_SUFFIXES = (".pdf", ".html", ".htm")


def _suffix_from_url(source_url: str) -> str:
    name = Path(urlparse(source_url).path).name.lower()
    suffix = Path(name).suffix
    if suffix not in _ALLOWED_SUFFIXES:
        raise ValueError(
            f"source_url must end with one of {_ALLOWED_SUFFIXES}: {source_url!r}"
        )
    # Normalize .htm to .html so get_source_path finds exactly one entry.
    return ".html" if suffix == ".htm" else suffix


def download_paper(
    paper_id: str,
    store: StorageBackend,
    *,
    source_url: str,
    timeout: float = _FETCH_TIMEOUT_SEC,
) -> Path:
    """Download a paper's source file and stage it in the paperstore.

    ``source_url`` is authoritative (from the mailing index). Returns the
    local path written by :meth:`StorageBackend.put_source`. Re-running
    with the same bytes is a no-op.
    """
    if not source_url:
        raise ValueError(
            f"download_paper requires source_url (from the mailing index). paper={paper_id}"
        )

    suffix = _suffix_from_url(source_url)
    logger.info("Downloading %s from %s", paper_id, source_url)
    resp = requests.get(
        source_url,
        timeout=timeout,
        headers={"User-Agent": _USER_AGENT},
    )
    resp.raise_for_status()
    path = store.put_source(paper_id, resp.content, suffix=suffix)
    logger.info("Staged %s at %s", paper_id, path)
    return path
