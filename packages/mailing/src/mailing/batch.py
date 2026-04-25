#
# Copyright (c) 2026 Greg Kaleka (greg@gregkaleka.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Idempotent corpus-level mailing operations.

``stage_mailing`` is the single entry point used by the CLI to fetch a
mailing's index and download every paper's source. Re-running with no
new papers (and no ``refetch=True``) does no network work.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Iterable

from paperstore import StorageBackend
from paperstore.errors import MissingSourceError

from mailing.download import download_paper as _default_download_paper
from mailing.scrape import fetch_papers_for_mailing as _default_fetch

logger = logging.getLogger(__name__)


def stage_mailing(
    mailing_id: str,
    store: StorageBackend,
    *,
    refetch: bool = False,
    papers: set[str] | None = None,
    fetch_papers: Callable[[str], list[dict]] | None = None,
    download: Callable[..., Path] | None = None,
) -> dict:
    """Fetch a mailing's index and stage every paper's source.

    Idempotent: a re-run with the same papers and ``refetch=False`` is a
    no-op for the network (the index is still upserted to refresh any
    metadata, but ``upsert_mailing_index`` preserves ``added`` timestamps).

    Args:
        mailing_id: e.g. ``"2026-04"``.
        store: paperstore backend rooted at the workspace.
        refetch: if True, re-download sources even when already staged.
        papers: optional uppercase paper-id filter; only these are staged.
        fetch_papers: injection seam for tests; defaults to
            ``mailing.scrape.fetch_papers_for_mailing``.
        download: injection seam for tests; defaults to
            ``mailing.download.download_paper``.

    Returns:
        Dict with counts: ``papers_in_index``, ``downloaded``, ``skipped``,
        ``no_url``, ``filtered_out``.
    """
    fetch = fetch_papers or _default_fetch
    do_download = download or _default_download_paper

    rows = fetch(mailing_id)
    if not rows:
        return {"papers_in_index": 0, "downloaded": 0, "skipped": 0, "no_url": 0, "filtered_out": 0}

    merged = store.upsert_mailing_index(mailing_id, rows)

    counts = {
        "papers_in_index": len(merged),
        "downloaded": 0,
        "skipped": 0,
        "no_url": 0,
        "filtered_out": 0,
    }

    for row in merged:
        pid = row["paper_id"]
        if papers is not None and pid.upper() not in papers:
            counts["filtered_out"] += 1
            continue

        url = row.get("url") or ""
        if not url:
            counts["no_url"] += 1
            logger.warning("Mailing row for %s has no url; skipping download", pid)
            continue

        if not refetch:
            try:
                store.get_source_path(pid)
                counts["skipped"] += 1
                continue
            except MissingSourceError:
                pass

        do_download(pid, store, source_url=url)
        counts["downloaded"] += 1

    return counts
