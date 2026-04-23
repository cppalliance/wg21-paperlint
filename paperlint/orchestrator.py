#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Paperlint pipeline orchestrator.

Runs Discovery -> Quote Verification -> Gate -> Evaluation Writer on a single paper.
Model calls are delegated to ``paperlint.llm`` (OpenRouter / OpenAI-compatible).
"""

import hashlib
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import requests

from paperlint.credentials import ensure_api_keys
from paperlint.llm import OPENROUTER_MODEL, build_client
from paperlint.models import SCHEMA_VERSION
from paperlint.pipeline import (
    PROMPTS_DIR,
    RUBRIC_PATH,
    step_discovery,
    step_gate,
    step_metadata,
    step_summary_writer,
    step_verify_quotes,
)
from paperlint.storage import JsonBackend, StorageBackend
from paperlint.suppress import step_suppress_known_fps

_PKG_ROOT = Path(__file__).resolve().parent

_FETCH_TIMEOUT_SEC = 120


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=_PKG_ROOT,
            stderr=subprocess.DEVNULL,
        ).decode().strip()[:12]
    except Exception:
        return "unknown"


def prompt_hash() -> str:
    files = sorted(PROMPTS_DIR.rglob("*.md")) + [RUBRIC_PATH]
    content = b"".join(f.read_bytes() for f in files if f.exists())
    return hashlib.sha256(content).hexdigest()[:12]


def fetch_paper(paper_id: str, cache_dir: Path | None = None, source_url: str = "") -> Path:
    """Fetch a WG21 document by ID using the canonical URL from the mailing index.

    source_url is required — it is the authoritative URL from the mailing index
    (cells[0] href). No year or extension guessing; no brute-force URL scan.
    """
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
        print(f"  Found cached: {local}")
        return local
    print(f"  Downloading: {source_url}")
    resp = requests.get(source_url, timeout=_FETCH_TIMEOUT_SEC, stream=True)
    resp.raise_for_status()
    local.write_bytes(resp.content)
    print(f"  Downloaded: {local}")
    return local


def _resolve_storage(
    workspace_dir: Path | None, storage: StorageBackend | None
) -> StorageBackend:
    if storage is not None:
        return storage
    if workspace_dir is None:
        raise ValueError("Either workspace_dir or storage must be provided.")
    return JsonBackend(workspace_dir)


def convert_one_paper(
    paper_id: str,
    *,
    workspace_dir: Path | None = None,
    source_url: str,
    mailing_meta: dict,
    storage: StorageBackend | None = None,
) -> dict:
    """Fetch a paper and convert it to markdown, no LLM calls.

    Writes ``paper.md`` and ``meta.json`` for the paper through the storage
    backend (default: a ``JsonBackend`` rooted at ``workspace_dir``). Used by
    both the convert-only CLI subcommand and ``run_paper_eval`` as the
    first stage of the AI pipeline.
    """
    paper_id = paper_id.strip().upper()
    if mailing_meta is None:
        raise ValueError(
            "convert_one_paper requires mailing_meta (authoritative from open-std.org)."
        )
    backend = _resolve_storage(workspace_dir, storage)

    print(f"Fetching {paper_id}...")
    paper_path = fetch_paper(paper_id, source_url=source_url)

    clean_text, meta = step_metadata(paper_path, mailing_meta)

    meta_path = backend.write_meta_json(paper_id, asdict(meta))
    paper_md_path = backend.write_paper_md(paper_id, clean_text)

    return {
        "paper_id": paper_id,
        "paper_path": paper_path,
        "paper_md_path": paper_md_path,
        "meta_path": meta_path,
        "meta": meta,
        "clean_text": clean_text,
    }


def _base_eval_json(source_url: str, paper_id: str, mailing_meta: dict | None) -> dict:
    """Build the skeleton eval JSON with whatever metadata is available."""
    if mailing_meta:
        title = mailing_meta.get("title", "Unknown")
        authors = mailing_meta.get("authors", [])
        audience = mailing_meta.get("subgroup", "Unknown")
    else:
        title = "Unknown"
        authors = []
        audience = "Unknown"

    return {
        "schema_version": SCHEMA_VERSION,
        "paperlint_sha": git_sha(),
        "prompt_hash": prompt_hash(),
        "source_url": source_url,
        "pipeline_status": "failed",
        "paper": paper_id.upper(),
        "title": title,
        "authors": authors,
        "audience": audience,
        "paper_type": "",
        "generated": datetime.now(timezone.utc).isoformat(),
        "model": OPENROUTER_MODEL,
        "findings_discovered": 0,
        "findings_passed": 0,
        "findings_rejected": 0,
        "summary": "",
        "findings": [],
        "references": [],
    }


def run_paper_eval(
    paper_ref: str,
    *,
    workspace_dir: Path | None = None,
    source_url: str = "",
    mailing_meta: dict | None = None,
    storage: StorageBackend | None = None,
    discovery_passes: int = 3,
) -> dict:
    """Evaluate one paper. Always writes an evaluation.json, even on failure.

    mailing_meta is the authoritative metadata from open-std.org's mailing index;
    it must be supplied by the caller (cmd_eval / cmd_run resolve it via
    fetch_papers_for_mailing).
    """
    paper_id = paper_ref.strip().upper()
    if mailing_meta is None:
        raise ValueError(
            "run_paper_eval requires mailing_meta (authoritative from open-std.org). "
            "Callers must resolve the paper through fetch_papers_for_mailing."
        )

    backend = _resolve_storage(workspace_dir, storage)
    ensure_api_keys()
    client = build_client()

    # Stage 1: convert (fetch + tomd + write paper.md/meta.json).
    try:
        conv = convert_one_paper(
            paper_id,
            source_url=source_url,
            mailing_meta=mailing_meta,
            storage=backend,
        )
    except Exception as e:
        print(f"  FETCH/CONVERT FAILED: {paper_id} — {e}")
        eval_json = _base_eval_json(source_url, paper_id, mailing_meta)
        eval_json["summary"] = "This paper could not be evaluated due to a document retrieval issue."
        backend.write_evaluation_json(paper_id, eval_json)
        return eval_json

    clean_text = conv["clean_text"]
    meta = conv["meta"]

    # Step 1: Discovery → Quote verification → Gate
    try:
        findings = step_discovery(
            client, clean_text, meta, passes=discovery_passes
        )
        raw_discovered = len(findings)

        findings_path = backend.write_intermediate(
            paper_id, "1-findings", [asdict(f) for f in findings]
        )
        print(f"  Written: {findings_path}")

        findings = step_verify_quotes(findings, clean_text)

        gated = step_gate(client, clean_text, meta, findings)

        backend.write_intermediate(
            paper_id,
            "2-gate",
            [
                {"finding_number": g.finding.number, "verdict": g.verdict, "reason": g.reason}
                for g in gated
            ],
        )

    except Exception as e:
        print(f"  ANALYSIS FAILED: {paper_id} — {e}")
        eval_json = _base_eval_json(source_url, paper_id, mailing_meta)
        eval_json["pipeline_status"] = "partial"
        eval_json["title"] = meta.title
        eval_json["authors"] = meta.authors
        eval_json["audience"] = meta.target_group
        eval_json["paper_type"] = meta.paper_type
        eval_json["summary"] = "This paper could not be fully evaluated due to an analysis issue."
        backend.write_evaluation_json(paper_id, eval_json)
        return eval_json

    # Step 2b: Known-FP suppression (post-gate filter)
    gated, suppressed = step_suppress_known_fps(gated, meta)
    backend.write_intermediate(paper_id, "2c-suppressed", suppressed)

    # Step 3: Summary
    passed = [g for g in gated if g.verdict == "PASS"]
    summary = step_summary_writer(client, meta, len(passed))

    # Step 4: Assembly
    references = []
    ref_counter = 1
    output_findings = []

    for gf in passed:
        f = gf.finding
        finding_refs = []
        for ev in f.evidence:
            if ev.verified:
                ref = {
                    "number": ref_counter,
                    "location": ev.location,
                    "quote": ev.quote,
                    "verified": True,
                }
                if ev.extracted_char_start is not None:
                    ref["extracted_char_start"] = ev.extracted_char_start
                    ref["extracted_char_end"] = ev.extracted_char_end
                references.append(ref)
                finding_refs.append(ref_counter)
                ref_counter += 1
        output_findings.append(
            {
                "location": f.evidence[0].location if f.evidence else "",
                "description": f.defect,
                "category": f.category,
                "correction": f.correction,
                "references": finding_refs,
            }
        )

    eval_json = {
        "schema_version": SCHEMA_VERSION,
        "paperlint_sha": git_sha(),
        "prompt_hash": prompt_hash(),
        "source_url": source_url,
        "pipeline_status": "complete",
        "paper": meta.paper,
        "title": meta.title,
        "authors": meta.authors,
        "audience": meta.target_group,
        "paper_type": meta.paper_type,
        "generated": meta.run_timestamp,
        "model": meta.model,
        "findings_discovered": raw_discovered,
        "findings_passed": len(passed),
        "findings_rejected": len([g for g in gated if g.verdict == "REJECT"]),
        "summary": summary,
        "findings": output_findings,
        "references": references,
    }

    eval_path = backend.write_evaluation_json(paper_id, eval_json)

    print(f"\n{'=' * 60}")
    print(f"Pipeline complete. Deliverable: {eval_path} + paper.md")
    print(f"{'=' * 60}")

    return eval_json
