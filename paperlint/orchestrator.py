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

On convert or analysis failure, ``evaluation.json`` includes ``failure_stage``,
``failure_type``, and ``failure_message``; optional ``failure_traceback`` when
``PAPERLINT_ERROR_TRACEBACK=1``. See the repository README.
"""

import hashlib
import json
import os
import subprocess
import sys
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import requests

from paperlint.credentials import ensure_api_keys
from paperlint.logutil import configure_paperlint_file_logging_if_needed, get_paperlint_logger
from paperlint.llm import OPENROUTER_MODEL, build_client
from paperlint.models import (
    SCHEMA_VERSION,
    Evaluation,
    OutputFinding,
    PaperMeta,
    Reference,
    to_dict,
)
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
    backend (default: a ``JsonBackend`` rooted at ``workspace_dir``). Invoked
    from the **convert** CLI only. ``run``/``eval`` load existing files via
    :func:`load_converted_paper` instead of calling this to avoid duplicate work.
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


def load_converted_paper(
    paper_id: str,
    *,
    workspace_dir: Path | None = None,
    storage: StorageBackend | None = None,
) -> tuple[str, PaperMeta]:
    """Load ``paper.md`` and ``meta.json`` from the workspace (after ``paperlint convert``).

    Raises:
        FileNotFoundError: if either file is missing or ``meta.json`` is invalid.
    """
    backend = _resolve_storage(workspace_dir, storage)
    if not isinstance(backend, JsonBackend):
        raise TypeError("load_converted_paper requires a JsonBackend (pass workspace_dir).")
    pid = paper_id.strip().upper()
    pdir = backend.workspace_dir / pid
    md_path = pdir / "paper.md"
    meta_path = pdir / "meta.json"
    if not md_path.is_file() or not meta_path.is_file():
        raise FileNotFoundError(
            f"Missing converted paper artifacts for {pid}. "
            f"Run: python -m paperlint convert <mailing-id> --workspace-dir {backend.workspace_dir} "
            f"(use --papers {pid} to convert only this paper). "
            f"Expected {md_path} and {meta_path}."
        )
    raw = json.loads(meta_path.read_text(encoding="utf-8"))
    meta = PaperMeta.from_dict(raw)
    return md_path.read_text(encoding="utf-8"), meta


def _base_evaluation(
    source_url: str, paper_id: str, mailing_meta: dict | None
) -> Evaluation:
    """Build the skeleton :class:`Evaluation` with whatever metadata is available."""
    if mailing_meta:
        title = mailing_meta.get("title", "Unknown")
        authors = list(mailing_meta.get("authors", []) or [])
        audience = mailing_meta.get("subgroup", "Unknown")
    else:
        title = "Unknown"
        authors = []
        audience = "Unknown"

    return Evaluation(
        schema_version=SCHEMA_VERSION,
        paperlint_sha=git_sha(),
        prompt_hash=prompt_hash(),
        source_url=source_url,
        pipeline_status="failed",
        paper=paper_id.upper(),
        title=title,
        authors=authors,
        audience=audience,
        paper_type="",
        generated=datetime.now(timezone.utc).isoformat(),
        model=OPENROUTER_MODEL,
        findings_discovered=0,
        findings_passed=0,
        findings_rejected=0,
        summary="",
    )


def _wants_error_traceback_in_json() -> bool:
    v = os.environ.get("PAPERLINT_ERROR_TRACEBACK", "").strip().lower()
    return v in ("1", "true", "yes")


def _apply_eval_failure(evaluation: Evaluation, stage: str, exc: Exception) -> None:
    """Attach structured failure data for debugging (additive; optional traceback)."""
    evaluation.failure_stage = stage
    evaluation.failure_type = type(exc).__name__
    evaluation.failure_message = str(exc)
    if _wants_error_traceback_in_json():
        evaluation.failure_traceback = traceback.format_exc()


def run_paper_eval(
    paper_ref: str,
    *,
    workspace_dir: Path | None = None,
    source_url: str = "",
    mailing_meta: dict | None = None,
    storage: StorageBackend | None = None,
    discovery_passes: int = 3,
) -> dict:
    """Evaluate one paper. Always writes an evaluation.json, even on analysis failure.

    Does **not** run conversion: ``paper.md`` and ``meta.json`` must already exist
    (``paperlint convert``). On missing artifacts, raises ``FileNotFoundError``.

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
    wdir = Path(workspace_dir) if workspace_dir is not None else None
    configure_paperlint_file_logging_if_needed(wdir)
    _log = get_paperlint_logger()
    ensure_api_keys()
    client = build_client()

    # Stage 1: load prior conversion (``paperlint convert``); do not re-fetch or re-tomd.
    try:
        clean_text, meta = load_converted_paper(
            paper_id, workspace_dir=workspace_dir, storage=backend
        )
    except FileNotFoundError:
        raise
    except Exception as e:
        print(
            f"  LOAD CONVERTED PAPER FAILED: {paper_id} — {e}",
            file=sys.stderr,
        )
        _log.exception("LOAD CONVERTED PAPER FAILED: %s", paper_id, exc_info=True)
        raise

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
        print(
            f"  ANALYSIS FAILED: {paper_id} — {e}",
            file=sys.stderr,
        )
        _log.exception("ANALYSIS FAILED: %s", paper_id, exc_info=True)
        evaluation = _base_evaluation(source_url, paper_id, mailing_meta)
        evaluation.pipeline_status = "partial"
        evaluation.title = meta.title
        evaluation.authors = meta.authors
        evaluation.audience = meta.target_group
        evaluation.paper_type = meta.paper_type
        evaluation.summary = "This paper could not be fully evaluated due to an analysis issue."
        _apply_eval_failure(evaluation, "analysis", e)
        eval_json = to_dict(evaluation)
        backend.write_evaluation_json(paper_id, eval_json)
        return eval_json

    # Step 2b: Known-FP suppression (post-gate filter)
    gated, suppressed = step_suppress_known_fps(gated, meta)
    backend.write_intermediate(paper_id, "2c-suppressed", suppressed)

    # Step 3: Summary
    passed = [g for g in gated if g.verdict == "PASS"]
    summary = step_summary_writer(client, meta, len(passed))

    # Step 4: Assembly
    references: list[Reference] = []
    ref_counter = 1
    output_findings: list[OutputFinding] = []

    for gf in passed:
        f = gf.finding
        finding_refs: list[int] = []
        for ev in f.evidence:
            if ev.verified:
                references.append(
                    Reference(
                        number=ref_counter,
                        location=ev.location,
                        quote=ev.quote,
                        verified=True,
                        extracted_char_start=ev.extracted_char_start,
                        extracted_char_end=ev.extracted_char_end,
                    )
                )
                finding_refs.append(ref_counter)
                ref_counter += 1
        output_findings.append(
            OutputFinding(
                location=f.evidence[0].location if f.evidence else "",
                description=f.defect,
                category=f.category,
                correction=f.correction,
                references=finding_refs,
            )
        )

    evaluation = Evaluation(
        schema_version=SCHEMA_VERSION,
        paperlint_sha=git_sha(),
        prompt_hash=prompt_hash(),
        source_url=source_url,
        pipeline_status="complete",
        paper=meta.paper,
        title=meta.title,
        authors=meta.authors,
        audience=meta.target_group,
        paper_type=meta.paper_type,
        generated=meta.run_timestamp,
        model=meta.model,
        findings_discovered=raw_discovered,
        findings_passed=len(passed),
        findings_rejected=len([g for g in gated if g.verdict == "REJECT"]),
        summary=summary,
        findings=output_findings,
        references=references,
    )
    eval_json = to_dict(evaluation)

    eval_path = backend.write_evaluation_json(paper_id, eval_json)

    print(f"\n{'=' * 60}")
    print(f"Pipeline complete. Deliverable: {eval_path} + paper.md")
    print(f"{'=' * 60}")

    return eval_json
