#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Mailing CLI: scrape an open-std.org mailing index and stage paper sources.

Usage::

    python -m mailing 2026-04 --workspace-dir ./data              # index + all sources (idempotent)
    python -m mailing 2026-04 --index-only --workspace-dir ./data # index only, no downloads
    python -m mailing 2026-04 --refetch --workspace-dir ./data    # re-download every source
    python -m mailing 2026-04/P3642R4 --workspace-dir ./data      # one paper (still idempotent)
    python -m mailing 2026-04 --paper P3642R4 -p P3700R0 --workspace-dir ./data
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from paperstore import JsonBackend
from paperstore.errors import MissingSourceError

from mailing.batch import stage_mailing
from mailing.download import download_paper
from mailing.scrape import fetch_papers_for_mailing

_REF_RE = re.compile(
    r"^(?P<mailing>\d{4}-\d{2})(?:/(?P<paper>[A-Za-z][A-Za-z0-9\-]*))?$"
)


def _stage_one_paper(
    mailing_id: str,
    paper_id: str,
    store: JsonBackend,
    *,
    refetch: bool,
) -> int:
    """Download a single paper's source. Idempotent unless ``refetch``."""
    papers = fetch_papers_for_mailing(mailing_id)
    if not papers:
        print(f"No papers found for mailing {mailing_id}", file=sys.stderr)
        return 1
    merged = store.upsert_mailing_index(mailing_id, papers)

    row = next(
        (p for p in merged if p["paper_id"].lower() == paper_id.lower()), None
    )
    if row is None:
        print(
            f"Error: {paper_id} not found in mailing {mailing_id}.",
            file=sys.stderr,
        )
        return 1

    source_url = row.get("url") or ""
    if not source_url:
        print(f"Error: {paper_id} has no url in the mailing row.", file=sys.stderr)
        return 1

    if not refetch:
        try:
            existing = store.get_source_path(paper_id)
            print(f"Already staged: {paper_id} at {existing}")
            return 0
        except MissingSourceError:
            pass

    path = download_paper(paper_id, store, source_url=source_url)
    print(f"Staged {paper_id} at {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="mailing",
        description="Scrape a WG21 mailing and stage paper sources (idempotent).",
    )
    parser.add_argument(
        "reference",
        help="Mailing id (e.g. 2026-04) or <mailing-id>/<paper-id>.",
    )
    parser.add_argument(
        "--workspace-dir",
        required=True,
        metavar="DIR",
        type=Path,
        help="Paperstore JSON backend root.",
    )
    parser.add_argument(
        "--index-only",
        action="store_true",
        help="Write the mailing index only; do not download any sources.",
    )
    parser.add_argument(
        "--refetch",
        action="store_true",
        help="Re-download every source, even if already staged.",
    )
    parser.add_argument(
        "-p", "--paper",
        action="append",
        default=[],
        metavar="PAPER_ID",
        help="Restrict to these paper ids (repeatable). Mailing-only ref.",
    )
    parser.add_argument(
        "--papers",
        default=None,
        metavar="IDS",
        help="Comma-separated paper-id filter (mailing-only ref).",
    )
    args = parser.parse_args()

    m = _REF_RE.match(args.reference.strip())
    if not m:
        print(
            f"Error: reference must be <mailing-id> or <mailing-id>/<paper-id>, got {args.reference!r}",
            file=sys.stderr,
        )
        return 2
    mailing_id = m.group("mailing")
    paper_id = m.group("paper")

    if paper_id is not None and (args.index_only or args.paper or args.papers):
        print(
            "Error: --index-only / --paper / --papers are only valid for the mailing-only form.",
            file=sys.stderr,
        )
        return 2

    store = JsonBackend(args.workspace_dir)

    if paper_id is not None:
        return _stage_one_paper(mailing_id, paper_id, store, refetch=args.refetch)

    if args.index_only:
        papers = fetch_papers_for_mailing(mailing_id)
        if not papers:
            print(f"No papers found for mailing {mailing_id}", file=sys.stderr)
            return 1
        store.upsert_mailing_index(mailing_id, papers)
        return 0

    filter_set: set[str] | None = None
    if args.paper or args.papers:
        ids: list[str] = list(args.paper)
        if args.papers:
            ids.extend(p for p in args.papers.split(",") if p.strip())
        filter_set = {p.strip().upper() for p in ids if p.strip()}

    counts = stage_mailing(
        mailing_id, store, refetch=args.refetch, papers=filter_set
    )
    if counts["papers_in_index"] == 0:
        print(f"No papers found for mailing {mailing_id}", file=sys.stderr)
        return 1

    print(
        f"Mailing {mailing_id}: {counts['papers_in_index']} papers in index, "
        f"{counts['downloaded']} downloaded, {counts['skipped']} already staged, "
        f"{counts['no_url']} without url, {counts['filtered_out']} filtered out."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
