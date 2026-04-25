#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Paperlint CLI — evaluate WG21 papers for mechanically verifiable defects.

Two-step flow (no duplicate conversion in eval/run):

1. **convert** — fetch sources and build ``paper.md`` + ``meta.json`` (no LLM).
   Limit work with ``--papers P1,P2`` or a single ``--paper P1``.
2. **eval** (one paper) or **run** (batch) — load those files and run the LLM
   pipeline to ``evaluation.json`` (requires ``OPENROUTER_API_KEY``).

Example::

    paperlint convert 2026-02 --paper P3642R4
    paperlint eval 2026-02/P3642R4

The open-std.org mailing index is authoritative for paper metadata. Every
``eval``/``run``/``convert`` run refreshes ``mailings/<id>.json``. Local file
paths and bare paper ids are not accepted.

``--workspace-dir`` (alias: ``--output-dir``) is the JSON-backend root: the same
directory is written and read for mailing indices, converted papers, and
evaluations. It defaults to ``$PAPERFLOW_WORKSPACE`` or ``./data``. This is
the only on-disk backend today; a Postgres backend may be added later via
the storage API.
"""

import argparse
import json
import re
import sys
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from paperlint.logutil import configure_paperlint_console_logging
from paperlint.models import (
    SCHEMA_VERSION,
    FailureEntry,
    IndexPaperEntry,
    MailingIndex,
    RoomEntry,
    to_dict,
)
from paperlint.orchestrator import (
    convert_one_paper,
    git_sha,
    prompt_hash,
    run_paper_eval,
)
from paperstore import WORKSPACE_ENV_VAR, JsonBackend, default_workspace_dir

_WORKSPACE_DIR_HELP = (
    "Workspace directory: mailings/<id>.json, per-paper dirs (paper.md, "
    "evaluation.json, …), and run's index.json. Same path is read and written. "
    f"Alias: --output-dir. Default: ${WORKSPACE_ENV_VAR} or ./data."
)


def _add_workspace_dir_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--workspace-dir",
        "--output-dir",
        dest="workspace_dir",
        metavar="DIR",
        default=default_workspace_dir(),
        help=_WORKSPACE_DIR_HELP,
    )


def _backend_for(workspace_dir: Path) -> JsonBackend:
    """Construct the default JSON storage backend rooted at ``workspace_dir``.

    Centralized here so a future ``--storage postgres://...`` flag can be
    added in one place without touching every CLI command.
    """
    return JsonBackend(workspace_dir)


def _eval_one_paper(
    paper_ref: str,
    workspace_dir: Path,
    source_url: str = "",
    mailing_meta: dict | None = None,
    *,
    discovery_passes: int = 3,
) -> dict:
    try:
        result = run_paper_eval(
            paper_ref,
            workspace_dir=workspace_dir,
            source_url=source_url,
            mailing_meta=mailing_meta,
            discovery_passes=discovery_passes,
        )
        return {"paper": paper_ref, "status": "ok", "result": result}
    except Exception as e:
        traceback.print_exc()
        return {"paper": paper_ref, "status": "error", "error": str(e)}


def _convert_one(
    paper_ref: str,
    workspace_dir: Path,
    source_url: str,
    mailing_meta: dict,
) -> dict:
    try:
        result = convert_one_paper(
            paper_ref,
            workspace_dir=workspace_dir,
            source_url=source_url,
            mailing_meta=mailing_meta,
        )
        return {
            "paper": paper_ref,
            "status": "ok",
            "paper_md": str(result["paper_md_path"]),
            "meta_path": str(result["meta_path"]),
        }
    except Exception as e:
        traceback.print_exc()
        return {"paper": paper_ref, "status": "error", "error": str(e)}


def _failure_entry(r: dict) -> FailureEntry:
    if r["status"] == "error":
        return FailureEntry(paper=r["paper"], error=r.get("error", ""))
    res = r.get("result") or {}
    return FailureEntry(
        paper=res.get("paper", r["paper"]),
        pipeline_status=res.get("pipeline_status"),
        summary=res.get("summary", ""),
        failure_stage=res.get("failure_stage"),
        failure_type=res.get("failure_type"),
        failure_message=res.get("failure_message"),
        failure_traceback=res.get("failure_traceback"),
    )


def _build_index(workspace_dir: Path, mailing_id: str, results: list[dict]) -> dict:
    succeeded = [
        r for r in results
        if r["status"] == "ok"
        and r.get("result", {}).get("pipeline_status") == "complete"
    ]
    failed = [
        r for r in results
        if r["status"] == "error"
        or r.get("result", {}).get("pipeline_status") in ("failed", "partial")
    ]
    partial_count = sum(
        1 for r in results
        if r.get("result", {}).get("pipeline_status") == "partial"
    )

    rooms: dict[str, RoomEntry] = defaultdict(RoomEntry)
    papers_summary: list[IndexPaperEntry] = []

    for r in succeeded:
        ev = r["result"]
        paper_id = ev.get("paper", r["paper"])
        audience = ev.get("audience", "Unknown")
        n_findings = ev.get("findings_passed", 0)

        for room in [a.strip() for a in audience.split(",")]:
            if room:
                rooms[room].papers.append(paper_id)
                rooms[room].total_findings += n_findings

        papers_summary.append(
            IndexPaperEntry(
                paper=paper_id,
                title=ev.get("title", ""),
                audience=audience,
                findings_passed=n_findings,
                findings_discovered=ev.get("findings_discovered", 0),
            )
        )

    index = MailingIndex(
        schema_version=SCHEMA_VERSION,
        paperlint_sha=git_sha(),
        prompt_hash=prompt_hash(),
        mailing_id=mailing_id,
        generated=datetime.now(timezone.utc).isoformat(),
        total_papers=len(results),
        succeeded=len(succeeded),
        failed=len(failed),
        partial=partial_count,
        rooms={k: rooms[k] for k in sorted(rooms)},
        papers=sorted(papers_summary, key=lambda p: p.findings_passed),
        failed_papers=[_failure_entry(r) for r in failed] if failed else None,
    )

    return to_dict(index)


_EVAL_CONTRACT_MSG = (
    "eval expects <mailing-id>/<paper-id> (e.g. 2026-02/P3642R4). "
    "The open-std.org mailing index is authoritative; local file paths and "
    "bare paper ids are not accepted. To evaluate a cached local file, drop "
    "it into .paperlint_cache/ and invoke via its mailing/paper-id."
)

_EVAL_REF_RE = re.compile(r"^(?P<mailing>\d{4}-\d{2})/(?P<paper>[A-Za-z][A-Za-z0-9\-]*)$")

_EPILOG_CONVERT = (
    "Only paper ids listed in --papers and/or --paper are downloaded and "
    "converted (not the whole mailing). Run eval or run after this step."
)
_EPILOG_RUN = (
    "Evaluates papers that already have paper.md and meta.json (run convert first). "
    "Use --papers / --paper to limit which papers to process."
)
_EPILOG_EVAL = (
    "Loads paper.md and meta.json from the workspace; run "
    "'paperlint convert <mailing> --paper <id>' first if missing."
)


def _parse_papers_filter(papers_arg: str | None) -> set[str] | None:
    """Return uppercase paper ids, or None if the argument is empty (meaning no filter)."""
    if not papers_arg or not str(papers_arg).strip():
        return None
    return {p.strip().upper() for p in str(papers_arg).split(",") if p.strip()}


def _merge_paper_selectors(
    single: str | None, comma_list: str | None
) -> str | None:
    """Join ``--paper`` and ``--papers`` into a comma string for :func:`_parse_papers_filter`."""
    parts: list[str] = []
    if single and str(single).strip():
        parts.append(str(single).strip())
    if comma_list and str(comma_list).strip():
        parts.extend(
            p.strip() for p in str(comma_list).split(",") if p and str(p).strip()
        )
    if not parts:
        return None
    return ",".join(parts)


def _filter_papers_list(
    papers: list[dict], mailing_id: str, want: set[str] | None, *, what: str
) -> list[dict]:
    """If *want* is set, keep only those paper_id (case-insensitive) and warn on unknown ids."""
    if not want:
        return list(papers)
    have = {p["paper_id"].upper() for p in papers}
    missing = sorted(want - have)
    if missing:
        print(
            f"Warning: {what} {mailing_id!r} has no paper_id(s): {', '.join(missing)}",
            file=sys.stderr,
        )
    out = [p for p in papers if p["paper_id"].upper() in want]
    return out


def _parse_eval_ref(ref: str) -> tuple[str, str]:
    """Parse a <mailing-id>/<paper-id> reference. Raise ValueError on violation."""
    m = _EVAL_REF_RE.match(ref.strip())
    if not m:
        raise ValueError(f"invalid eval ref {ref!r}. {_EVAL_CONTRACT_MSG}")
    return m.group("mailing"), m.group("paper").upper()


def cmd_eval(args: argparse.Namespace) -> int:
    from mailing.scrape import fetch_papers_for_mailing

    try:
        mailing_id, paper_id = _parse_eval_ref(args.paper)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    workspace_dir = Path(args.workspace_dir)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching mailing index for {mailing_id}...")
    papers = fetch_papers_for_mailing(mailing_id)
    if not papers:
        print(f"No papers found for mailing {mailing_id}", file=sys.stderr)
        return 1

    backend = _backend_for(workspace_dir)
    merged = backend.upsert_mailing_index(mailing_id, papers)

    meta = next((p for p in merged if p["paper_id"].lower() == paper_id.lower()), None)
    if not meta:
        print(
            f"Error: {paper_id} not found in mailing {mailing_id}. "
            f"Check the paper id or the mailing.",
            file=sys.stderr,
        )
        return 1

    try:
        run_paper_eval(
            paper_id,
            workspace_dir=workspace_dir,
            source_url=meta.get("url", ""),
            mailing_meta=meta,
            discovery_passes=args.discovery_passes,
        )
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


def cmd_run(args: argparse.Namespace) -> int:
    from mailing.scrape import fetch_papers_for_mailing

    workspace_dir = Path(args.workspace_dir)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    mailing_id = args.mailing_id
    max_cap = args.max_cap
    max_processes = args.max_processes if args.max_processes is not None else args.max_workers

    print(f"Fetching paper list for mailing {mailing_id}...")
    papers = fetch_papers_for_mailing(mailing_id)

    if not papers:
        print(f"No papers found for mailing {mailing_id}", file=sys.stderr)
        return 1

    backend = _backend_for(workspace_dir)
    merged = backend.upsert_mailing_index(mailing_id, papers)

    meta_by_id = {p["paper_id"]: p for p in merged}

    sel = _merge_paper_selectors(
        getattr(args, "paper", None), getattr(args, "papers", None)
    )
    pf = _parse_papers_filter(sel)
    if pf:
        papers = _filter_papers_list(papers, mailing_id, pf, what="mailing")
        if not papers:
            print("No papers to process after --papers filter.", file=sys.stderr)
            return 1
    if max_cap > 0:
        papers = papers[:max_cap]

    print(f"Processing {len(papers)} papers with {max_processes} workers...")

    results: list[dict] = []

    if max_processes == 1:
        for p in papers:
            pid = p["paper_id"]
            pm = meta_by_id.get(pid)
            result = _eval_one_paper(
                pid,
                workspace_dir,
                source_url=pm["url"] if pm else "",
                mailing_meta=pm,
                discovery_passes=args.discovery_passes,
            )
            results.append(result)
            status = "OK" if result["status"] == "ok" else "FAILED"
            print(f"\n  [{status}] {pid}")
    else:
        with ThreadPoolExecutor(max_workers=max_processes) as executor:
            futures = {}
            for p in papers:
                pid = p["paper_id"]
                pm = meta_by_id.get(pid)
                f = executor.submit(
                    _eval_one_paper,
                    pid,
                    workspace_dir,
                    pm["url"] if pm else "",
                    pm,
                    discovery_passes=args.discovery_passes,
                )
                futures[f] = pid
            for future in as_completed(futures):
                pid = futures[future]
                result = future.result()
                results.append(result)
                status = "OK" if result["status"] == "ok" else "FAILED"
                print(f"\n  [{status}] {pid}")

    index = _build_index(workspace_dir, mailing_id, results)
    index_path = workspace_dir / "index.json"
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

    succeeded = index["succeeded"]
    failed = index["failed"]
    total = index["total_papers"]
    print(f"\n{'=' * 60}")
    print(f"Mailing {mailing_id} complete: {succeeded}/{total} succeeded, {failed} failed")
    print(f"Rooms: {', '.join(index['rooms'].keys())}")
    print(f"Index: {index_path}")
    print(f"{'=' * 60}")

    return 0 if failed == 0 else 1


def cmd_convert(args: argparse.Namespace) -> int:
    """Fetch and convert all papers in a mailing to markdown — no AI eval.

    This is the standalone ingestion path: it satisfies directives 6 and 8
    by writing ``paper.md`` + ``meta.json`` per paper plus a fresh mailing
    index, with no LLM calls. The AI evaluation pipeline is opt-in via the
    ``run`` (or ``eval``) subcommand.
    """
    from mailing.scrape import fetch_papers_for_mailing

    workspace_dir = Path(args.workspace_dir)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    mailing_id = args.mailing_id
    max_cap = args.max_cap
    max_workers = args.max_workers

    print(f"Fetching paper list for mailing {mailing_id}...")
    papers = fetch_papers_for_mailing(mailing_id)
    if not papers:
        print(f"No papers found for mailing {mailing_id}", file=sys.stderr)
        return 1

    backend = _backend_for(workspace_dir)
    merged = backend.upsert_mailing_index(mailing_id, papers)

    meta_by_id = {p["paper_id"]: p for p in merged}

    sel = _merge_paper_selectors(
        getattr(args, "paper", None), getattr(args, "papers", None)
    )
    pf = _parse_papers_filter(sel)
    if pf:
        papers = _filter_papers_list(papers, mailing_id, pf, what="mailing")
        if not papers:
            print("No papers to convert after --papers filter.", file=sys.stderr)
            return 1
    if max_cap > 0:
        papers = papers[:max_cap]

    print(f"Converting {len(papers)} papers with {max_workers} workers...")

    results: list[dict] = []
    if max_workers == 1:
        for p in papers:
            pid = p["paper_id"]
            pm = meta_by_id.get(pid)
            r = _convert_one(pid, workspace_dir, pm["url"] if pm else "", pm)
            results.append(r)
            status = "OK" if r["status"] == "ok" else "FAILED"
            print(f"\n  [{status}] {pid}")
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for p in papers:
                pid = p["paper_id"]
                pm = meta_by_id.get(pid)
                f = executor.submit(
                    _convert_one,
                    pid,
                    workspace_dir,
                    pm["url"] if pm else "",
                    pm,
                )
                futures[f] = pid
            for future in as_completed(futures):
                pid = futures[future]
                r = future.result()
                results.append(r)
                status = "OK" if r["status"] == "ok" else "FAILED"
                print(f"\n  [{status}] {pid}")

    succeeded = sum(1 for r in results if r["status"] == "ok")
    failed = len(results) - succeeded
    print(f"\n{'=' * 60}")
    print(f"Convert {mailing_id} complete: {succeeded}/{len(results)} succeeded, {failed} failed")
    print(f"{'=' * 60}")
    return 0 if failed == 0 else 1


def cmd_mailing(args: argparse.Namespace) -> int:
    """Fetch and persist the ground-truth mailing index.

    Writes ``<workspace-dir>/mailings/<mailing-id>.json``. Idempotent: re-running
    keeps existing entries (and their original ``added`` timestamps) and
    appends only newly listed papers.
    """
    from mailing.scrape import fetch_papers_for_mailing

    mailing_id = args.mailing_id
    workspace_dir = Path(args.workspace_dir)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching mailing index for {mailing_id} from open-std.org...")
    papers = fetch_papers_for_mailing(mailing_id)
    if not papers:
        print(f"No papers found for mailing {mailing_id}", file=sys.stderr)
        return 1

    backend = _backend_for(workspace_dir)
    backend.upsert_mailing_index(mailing_id, papers)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="paperlint",
        description="Evaluate WG21 papers for mechanically verifiable defects",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase log verbosity (-v = INFO, -vv = DEBUG). Default is WARNING.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    eval_parser = subparsers.add_parser(
        "eval",
        help="Evaluate a single paper via the mailing index",
        epilog=_EPILOG_EVAL,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    eval_parser.add_argument(
        "paper",
        help="Paper reference in <mailing-id>/<paper-id> form (e.g. 2026-02/P3642R4)",
    )
    _add_workspace_dir_arg(eval_parser)
    eval_parser.add_argument(
        "--discovery-passes",
        type=int,
        default=3,
        help=(
            "Number of LLM discovery passes (default: 3). Each pass after the first is "
            "shown prior findings and asked to add only new ones."
        ),
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Evaluate all papers in a mailing",
        epilog=_EPILOG_RUN,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    run_parser.add_argument("mailing_id", help="Mailing identifier (e.g. 2026-02)")
    _add_workspace_dir_arg(run_parser)
    run_parser.add_argument("--max-cap", type=int, default=0, help="Max papers (0 = all)")
    run_parser.add_argument("--max-workers", type=int, default=10, help="Parallel workers")
    run_parser.add_argument(
        "--paper",
        default=None,
        metavar="PAPER",
        help="One paper id (convenience; can combine with --papers)",
    )
    run_parser.add_argument(
        "--papers",
        default=None,
        metavar="IDS",
        help="Comma-separated paper ids to evaluate, then --max-cap (default: entire mailing list)",
    )
    run_parser.add_argument("--max-processes", type=int, default=None, help=argparse.SUPPRESS)
    run_parser.add_argument(
        "--discovery-passes",
        type=int,
        default=3,
        help=(
            "Number of LLM discovery passes (default: 3). Each pass after the first is "
            "shown prior findings and asked to add only new ones."
        ),
    )

    convert_parser = subparsers.add_parser(
        "convert",
        help="Fetch and convert all papers in a mailing to markdown (no AI eval)",
        epilog=_EPILOG_CONVERT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    convert_parser.add_argument("mailing_id", help="Mailing identifier (e.g. 2026-02)")
    _add_workspace_dir_arg(convert_parser)
    convert_parser.add_argument("--max-cap", type=int, default=0, help="Max papers (0 = all)")
    convert_parser.add_argument("--max-workers", type=int, default=10, help="Parallel workers")
    convert_parser.add_argument(
        "--paper",
        default=None,
        metavar="PAPER",
        help="One paper id to convert (convenience; can combine with --papers)",
    )
    convert_parser.add_argument(
        "--papers",
        default=None,
        metavar="IDS",
        help="Comma-separated paper ids to convert, then --max-cap (default: entire mailing list)",
    )

    mailing_parser = subparsers.add_parser("mailing", help="Fetch and persist a mailing index")
    mailing_parser.add_argument("mailing_id", help="Mailing identifier (e.g. 2026-02)")
    _add_workspace_dir_arg(mailing_parser)

    args = parser.parse_args()
    configure_paperlint_console_logging(args.verbose)

    if args.command == "eval":
        return cmd_eval(args)
    elif args.command == "run":
        return cmd_run(args)
    elif args.command == "convert":
        return cmd_convert(args)
    elif args.command == "mailing":
        return cmd_mailing(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
