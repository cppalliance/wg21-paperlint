#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Mailing CLI: scrape an open-std.org mailing index, optionally download one paper.

Usage::

    python -m mailing 2026-02 --workspace-dir ./data              # index only
    python -m mailing 2026-02/P3642R4 --workspace-dir ./data      # index + source
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from paperstore import JsonBackend

from mailing.download import download_paper
from mailing.scrape import fetch_papers_for_mailing

_REF_RE = re.compile(
    r"^(?P<mailing>\d{4}-\d{2})(?:/(?P<paper>[A-Za-z][A-Za-z0-9\-]*))?$"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="mailing",
        description="Scrape a WG21 mailing index (and optionally stage one paper source).",
    )
    parser.add_argument(
        "reference",
        help="Mailing id (e.g. 2026-02) or <mailing-id>/<paper-id>.",
    )
    parser.add_argument(
        "--workspace-dir",
        required=True,
        metavar="DIR",
        type=Path,
        help="Paperstore JSON backend root.",
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

    store = JsonBackend(args.workspace_dir)

    print(f"Fetching mailing index for {mailing_id}...")
    papers = fetch_papers_for_mailing(mailing_id)
    if not papers:
        print(f"No papers found for mailing {mailing_id}", file=sys.stderr)
        return 1

    merged = store.upsert_mailing_index(mailing_id, papers)

    if paper_id is None:
        return 0

    row = next(
        (p for p in merged if p["paper_id"].lower() == paper_id.lower()), None
    )
    if row is None:
        print(
            f"Error: {paper_id} not found in mailing {mailing_id}.",
            file=sys.stderr,
        )
        return 1

    source_url = row.get("url", "")
    if not source_url:
        print(f"Error: {paper_id} has no url in the mailing row.", file=sys.stderr)
        return 1

    path = download_paper(paper_id, store, source_url=source_url)
    print(f"Staged {paper_id} at {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
