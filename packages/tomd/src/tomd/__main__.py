#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""tomd CLI: convert paperstore-staged WG21 papers to markdown.

Usage::

    python -m tomd P3642R4 --workspace-dir ./data
    python -m tomd 2026-04 --workspace-dir ./data            # all papers in mailing 2026-04
    python -m tomd P3642R4 P3700R0 --workspace-dir ./data    # multiple paper ids
    python -m tomd 2026-04 --workspace-dir ./data --qa       # batch QA scoring

Mailing-id positionals (matching ``YYYY-MM``) expand to every paper id
in that mailing's index. Run ``python -m mailing <mailing-id>
--workspace-dir DIR`` first to populate the index.

The pre-0.2 file-path interface (``tomd input.pdf``) is removed; stage
sources with ``python -m mailing`` first.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

from paperstore import JsonBackend
from paperstore.errors import (
    MissingMailingIndexError,
    MissingMetaError,
    MissingPaperMdError,
    MissingSourceError,
)

from tomd.api import convert_paper

_MAILING_RE = re.compile(r"^\d{4}-\d{2}$")


def expand_references(
    references: list[str], backend: JsonBackend
) -> list[str]:
    """Expand mailing ids in ``references`` to their paper-id rows.

    Each positional is either a mailing id (``YYYY-MM``, expanded via
    ``backend.list_mailing``) or a paper id (passed through, uppercased).
    Paper-id order is preserved within each input; mailing expansion
    follows the index's stored order.

    Raises ``MissingMailingIndexError`` if a mailing-id positional has no
    persisted index.
    """
    out: list[str] = []
    for ref in references:
        if _MAILING_RE.match(ref):
            rows = backend.list_mailing(ref)
            out.extend(row["paper_id"].upper() for row in rows)
        else:
            out.append(ref.upper())
    return out


def _cmd_convert(
    paper_ids: list[str], backend: JsonBackend, *, write_prompts: bool
) -> int:
    rc = 0
    for pid in paper_ids:
        try:
            convert_paper(pid, backend, write_prompts=write_prompts)
            print(f"Converted {pid}")
        except (MissingSourceError, MissingMetaError) as e:
            print(f"Skipping {pid}: {e}", file=sys.stderr)
            rc = max(rc, 2)
        except Exception as e:
            print(f"FAIL: {pid} -- {e}", file=sys.stderr)
            rc = max(rc, 1)
    return rc


def _cmd_qa(
    paper_ids: list[str],
    backend: JsonBackend,
    *,
    json_path: Path | None,
    workers: int,
    timeout: int,
) -> int:
    from tomd.lib.pdf.qa import run_qa_report

    md_files: list[Path] = []
    for pid in paper_ids:
        try:
            backend.get_paper_md(pid)
        except MissingPaperMdError:
            print(
                f"Skipping {pid}: no paper.md. Run convert first.",
                file=sys.stderr,
            )
            continue
        md_files.append(backend.workspace_dir / pid.upper() / "paper.md")

    if not md_files:
        print("No markdown files available for QA.", file=sys.stderr)
        return 1

    run_qa_report(md_files, json_path=json_path, workers=workers, timeout=timeout)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="tomd",
        description="Convert paperstore-staged WG21 papers to markdown.",
    )
    parser.add_argument(
        "references",
        nargs="+",
        metavar="REF",
        help="Paper ids (e.g. P3642R4) or mailing ids (e.g. 2026-04, expands to all).",
    )
    parser.add_argument(
        "--workspace-dir",
        required=True,
        metavar="DIR",
        type=Path,
        help="Paperstore JSON backend root.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--no-prompts",
        action="store_true",
        help="Skip writing the .prompts intermediate.",
    )
    parser.add_argument(
        "--qa",
        action="store_true",
        help="Run QA scoring against paper.md instead of converting.",
    )
    parser.add_argument(
        "--qa-json",
        type=Path,
        metavar="PATH",
        help="Write per-paper QA metrics as JSON to PATH (implies --qa).",
    )
    parser.add_argument("--workers", type=int, default=1, help="QA parallelism.")
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="QA straggler timeout in seconds.",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s: %(message)s")

    backend = JsonBackend(args.workspace_dir)

    try:
        paper_ids = expand_references(args.references, backend)
    except MissingMailingIndexError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    if not paper_ids:
        print("No papers to process.", file=sys.stderr)
        return 1

    if args.qa or args.qa_json:
        return _cmd_qa(
            paper_ids,
            backend,
            json_path=args.qa_json,
            workers=args.workers,
            timeout=args.timeout,
        )

    return _cmd_convert(paper_ids, backend, write_prompts=not args.no_prompts)


if __name__ == "__main__":
    sys.exit(main())
