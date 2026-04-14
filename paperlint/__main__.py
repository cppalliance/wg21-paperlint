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
    python -m paperlint eval P3642R4 --output-dir ./output/
    python -m paperlint run 2026-02 --output-dir ./data/ --max-cap 50 --max-processes 10
"""

import argparse
import json
import sys
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from paperlint.orchestrator import run_paper_eval, _git_sha, _prompt_hash, SCHEMA_VERSION


def _eval_one_paper(paper_ref: str, output_dir: Path) -> dict:
    try:
        result = run_paper_eval(paper_ref, output_dir=output_dir)
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
        "paperlint_sha": _git_sha(),
        "prompt_hash": _prompt_hash(),
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


def cmd_eval(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        run_paper_eval(args.paper, output_dir=output_dir)
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


def cmd_run(args: argparse.Namespace) -> int:
    from paperlint.mailing import fetch_mailing_paper_ids

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    mailing_id = args.mailing_id
    max_cap = args.max_cap
    max_processes = args.max_processes

    print(f"Fetching paper list for mailing {mailing_id}...")
    paper_ids = fetch_mailing_paper_ids(mailing_id)

    if not paper_ids:
        print(f"No papers found for mailing {mailing_id}", file=sys.stderr)
        return 1

    if max_cap > 0:
        paper_ids = paper_ids[:max_cap]

    print(f"Processing {len(paper_ids)} papers with {max_processes} workers...")

    results: list[dict] = []

    if max_processes == 1:
        for paper_id in paper_ids:
            result = _eval_one_paper(paper_id, output_dir)
            results.append(result)
            status = "OK" if result["status"] == "ok" else "FAILED"
            print(f"\n  [{status}] {paper_id}")
    else:
        with ThreadPoolExecutor(max_workers=max_processes) as executor:
            futures = {
                executor.submit(_eval_one_paper, pid, output_dir): pid
                for pid in paper_ids
            }
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


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="paperlint",
        description="Evaluate WG21 papers for mechanically verifiable defects",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    eval_parser = subparsers.add_parser("eval", help="Evaluate a single paper")
    eval_parser.add_argument("paper", help="Paper ID (e.g. P3642R4) or path to local file")
    eval_parser.add_argument("--output-dir", required=True, help="Output directory")

    run_parser = subparsers.add_parser("run", help="Evaluate all papers in a mailing")
    run_parser.add_argument("mailing_id", help="Mailing identifier (e.g. 2026-02)")
    run_parser.add_argument("--output-dir", required=True, help="Output directory")
    run_parser.add_argument("--max-cap", type=int, default=0, help="Max papers (0 = all)")
    run_parser.add_argument("--max-processes", type=int, default=10, help="Parallel workers")

    args = parser.parse_args()

    if args.command == "eval":
        return cmd_eval(args)
    elif args.command == "run":
        return cmd_run(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
