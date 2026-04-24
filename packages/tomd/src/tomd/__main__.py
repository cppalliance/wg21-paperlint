#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""tomd CLI: convert a paper staged in paperstore to markdown.

Usage::

    python -m tomd PAPER_ID --workspace-dir ./data
    python -m tomd PAPER_ID --workspace-dir ./data --qa
    python -m tomd PAPER_ID P2 P3 --workspace-dir ./data --qa --qa-json out.json

The old file-path CLI (``tomd input.pdf``) was removed in the 0.2
restructure; stage sources with ``python -m mailing`` first.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from paperstore import JsonBackend
from paperstore.errors import (
    MissingMetaError,
    MissingPaperMdError,
    MissingSourceError,
)

from tomd.api import convert_paper


def _cmd_convert(paper_id: str, backend: JsonBackend, *, write_prompts: bool) -> int:
    try:
        convert_paper(paper_id, backend, write_prompts=write_prompts)
    except MissingSourceError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except MissingMetaError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"FAIL: {paper_id} -- {e}", file=sys.stderr)
        return 1
    return 0


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
        "paper_ids",
        nargs="+",
        metavar="PAPER_ID",
        help="One or more paper ids (e.g. P3642R4). Multiple ids only supported with --qa.",
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

    if args.qa or args.qa_json:
        return _cmd_qa(
            args.paper_ids,
            backend,
            json_path=args.qa_json,
            workers=args.workers,
            timeout=args.timeout,
        )

    if len(args.paper_ids) > 1:
        parser.error("Multiple paper ids are only supported with --qa.")

    return _cmd_convert(
        args.paper_ids[0], backend, write_prompts=not args.no_prompts
    )


if __name__ == "__main__":
    sys.exit(main())
