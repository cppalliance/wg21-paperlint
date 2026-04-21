#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Paperlint CLI — evaluate WG21 papers for mechanically verifiable defects.

Usage:
    python -m paperlint eval 2026-02/P3642R4 --output-dir ./output/
    python -m paperlint run 2026-02 --output-dir ./data/ --max-cap 50 --max-workers 10

The open-std.org mailing index is authoritative for paper metadata (title,
authors, audience, paper_type, canonical URL). Every `eval` invocation names
the mailing and the paper id explicitly; local file paths and bare paper ids
are not accepted.
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

from paperlint.orchestrator import run_paper_eval, git_sha, prompt_hash, SCHEMA_VERSION


def _persist_mailing_index(papers: list[dict], index_path: Path) -> list[dict]:
    """Merge-persist a mailing index: keeps existing entries with their
    original added dates, appends new papers with current timestamp."""
    existing_by_id = {}
    if index_path.exists():
        for entry in json.loads(index_path.read_text()):
            existing_by_id[entry["paper_id"]] = entry

    now = datetime.now(timezone.utc).isoformat()
    merged = []
    new_count = 0
    for p in papers:
        if p["paper_id"] in existing_by_id:
            merged.append(existing_by_id[p["paper_id"]])
        else:
            p["added"] = now
            merged.append(p)
            new_count += 1
    merged.sort(key=lambda e: e["paper_id"])

    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Mailing index: {index_path} ({len(merged)} papers, {new_count} new)")
    return merged


def _eval_one_paper(paper_ref: str, output_dir: Path, source_url: str = "",
                    mailing_meta: dict | None = None) -> dict:
    try:
        result = run_paper_eval(paper_ref, output_dir=output_dir,
                                source_url=source_url, mailing_meta=mailing_meta)
        return {"paper": paper_ref, "status": "ok", "result": result}
    except Exception as e:
        traceback.print_exc()
        return {"paper": paper_ref, "status": "error", "error": str(e)}


def _build_index(output_dir: Path, mailing_id: str, results: list[dict]) -> dict:
    succeeded = [r for r in results if r["status"] == "ok" and r.get("result")]
    failed = [r for r in results if r["status"] == "error"]

    rooms: dict[str, dict] = defaultdict(lambda: {"papers": [], "total_findings": 0})
    papers_summary = []

    for r in succeeded:
        ev = r["result"]
        paper_id = ev.get("paper", r["paper"])
        audience = ev.get("audience", "Unknown")
        n_findings = ev.get("findings_passed", 0)

        for room in [a.strip() for a in audience.split(",")]:
            if room:
                rooms[room]["papers"].append(paper_id)
                rooms[room]["total_findings"] += n_findings

        papers_summary.append({
            "paper": paper_id,
            "title": ev.get("title", ""),
            "audience": audience,
            "findings_passed": n_findings,
            "findings_discovered": ev.get("findings_discovered", 0),
        })

    index = {
        "schema_version": SCHEMA_VERSION,
        "paperlint_sha": git_sha(),
        "prompt_hash": prompt_hash(),
        "mailing_id": mailing_id,
        "generated": datetime.now(timezone.utc).isoformat(),
        "total_papers": len(results),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "rooms": {k: dict(v) for k, v in sorted(rooms.items())},
        "papers": sorted(papers_summary, key=lambda p: p.get("findings_passed", 0)),
    }

    if failed:
        index["failed_papers"] = [{"paper": r["paper"], "error": r.get("error", "")} for r in failed]

    return index


_EVAL_CONTRACT_MSG = (
    "eval expects <mailing-id>/<paper-id> (e.g. 2026-02/P3642R4). "
    "The open-std.org mailing index is authoritative; local file paths and "
    "bare paper ids are not accepted. To evaluate a cached local file, drop "
    "it into .paperlint_cache/ and invoke via its mailing/paper-id."
)

_EVAL_REF_RE = re.compile(r"^(?P<mailing>\d{4}-\d{2})/(?P<paper>[A-Za-z][A-Za-z0-9\-]*)$")


def _parse_eval_ref(ref: str) -> tuple[str, str]:
    """Parse a <mailing-id>/<paper-id> reference. Raise ValueError on violation."""
    m = _EVAL_REF_RE.match(ref.strip())
    if not m:
        raise ValueError(_EVAL_CONTRACT_MSG)
    return m.group("mailing"), m.group("paper").upper()


def cmd_eval(args: argparse.Namespace) -> int:
    from paperlint.mailing import fetch_papers_for_mailing

    try:
        mailing_id, paper_id = _parse_eval_ref(args.paper)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching mailing index for {mailing_id}...")
    papers = fetch_papers_for_mailing(mailing_id)
    if not papers:
        print(f"No papers found for mailing {mailing_id}", file=sys.stderr)
        return 1

    index_path = output_dir.parent / "mailings" / f"{mailing_id}.json"
    merged = _persist_mailing_index(papers, index_path)

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
            output_dir=output_dir,
            source_url=meta.get("url", ""),
            mailing_meta=meta,
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
    from paperlint.mailing import fetch_papers_for_mailing

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    mailing_id = args.mailing_id
    max_cap = args.max_cap
    max_processes = args.max_processes if args.max_processes is not None else args.max_workers

    print(f"Fetching paper list for mailing {mailing_id}...")
    papers = fetch_papers_for_mailing(mailing_id)

    if not papers:
        print(f"No papers found for mailing {mailing_id}", file=sys.stderr)
        return 1

    # Persist mailing index as ground-truth record
    index_path = output_dir.parent / "mailings" / f"{mailing_id}.json"
    merged = _persist_mailing_index(papers, index_path)

    meta_by_id = {p["paper_id"]: p for p in merged}

    if max_cap > 0:
        papers = papers[:max_cap]

    print(f"Processing {len(papers)} papers with {max_processes} workers...")

    results: list[dict] = []

    if max_processes == 1:
        for p in papers:
            pid = p["paper_id"]
            pm = meta_by_id.get(pid)
            result = _eval_one_paper(pid, output_dir,
                                     source_url=pm["url"] if pm else "",
                                     mailing_meta=pm)
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
                    _eval_one_paper, pid, output_dir,
                    pm["url"] if pm else "",
                    pm,
                )
                futures[f] = pid
            for future in as_completed(futures):
                pid = futures[future]
                result = future.result()
                results.append(result)
                status = "OK" if result["status"] == "ok" else "FAILED"
                print(f"\n  [{status}] {pid}")

    index = _build_index(output_dir, mailing_id, results)
    index_path = output_dir / "index.json"
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


def cmd_mailing(args: argparse.Namespace) -> int:
    """Fetch and persist the ground-truth mailing index."""
    from paperlint.mailing import fetch_papers_for_mailing

    mailing_id = args.mailing_id
    output = Path(args.output)

    print(f"Fetching mailing index for {mailing_id} from open-std.org...")
    papers = fetch_papers_for_mailing(mailing_id)
    if not papers:
        print(f"No papers found for mailing {mailing_id}", file=sys.stderr)
        return 1

    _persist_mailing_index(papers, output)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="paperlint",
        description="Evaluate WG21 papers for mechanically verifiable defects",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    eval_parser = subparsers.add_parser(
        "eval",
        help="Evaluate a single paper via the mailing index",
    )
    eval_parser.add_argument(
        "paper",
        help="Paper reference in <mailing-id>/<paper-id> form (e.g. 2026-02/P3642R4)",
    )
    eval_parser.add_argument("--output-dir", required=True, help="Output directory")

    run_parser = subparsers.add_parser("run", help="Evaluate all papers in a mailing")
    run_parser.add_argument("mailing_id", help="Mailing identifier (e.g. 2026-02)")
    run_parser.add_argument("--output-dir", required=True, help="Output directory")
    run_parser.add_argument("--max-cap", type=int, default=0, help="Max papers (0 = all)")
    run_parser.add_argument("--max-workers", type=int, default=10, help="Parallel workers")
    run_parser.add_argument("--max-processes", type=int, default=None, help=argparse.SUPPRESS)

    mailing_parser = subparsers.add_parser("mailing", help="Fetch and persist a mailing index")
    mailing_parser.add_argument("mailing_id", help="Mailing identifier (e.g. 2026-02)")
    mailing_parser.add_argument("--output", default="mailings/{mailing_id}.json",
                                help="Output path (default: mailings/{mailing_id}.json)")

    args = parser.parse_args()

    if args.command == "mailing":
        if "{mailing_id}" in args.output:
            args.output = args.output.replace("{mailing_id}", args.mailing_id)

    if args.command == "eval":
        return cmd_eval(args)
    elif args.command == "run":
        return cmd_run(args)
    elif args.command == "mailing":
        return cmd_mailing(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
