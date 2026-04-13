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
All model calls route through OpenRouter (OpenAI-compatible).
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

import openai

from paperlint.credentials import ensure_api_keys, resolve_openrouter_base_url
from paperlint.extract import extract_text

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PKG_ROOT = Path(__file__).resolve().parent

OPENROUTER_MODEL = "anthropic/claude-opus-4.6"
OPENROUTER_SONNET = "anthropic/claude-sonnet-4.6"

SCHEMA_VERSION = "1"

THINKING_BUDGET = {
    "discovery": 40_000,
    "gate": 5_000,
    "eval_writer": 5_000,
}

MAX_TOKENS = {
    "discovery": 64_000,
    "gate": 8_192,
    "eval_writer": 8_192,
}

PROMPTS_DIR = _PKG_ROOT / "prompts"
RUBRIC_PATH = _PKG_ROOT / "rubric.md"

MAX_RETRIES = 3
RETRY_BASE_DELAY = 10


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=_PKG_ROOT,
            stderr=subprocess.DEVNULL,
        ).decode().strip()[:12]
    except Exception:
        return "unknown"


def _prompt_hash() -> str:
    files = sorted(PROMPTS_DIR.glob("*.md")) + [RUBRIC_PATH]
    content = b"".join(f.read_bytes() for f in files if f.exists())
    return hashlib.sha256(content).hexdigest()[:12]


def _log_error(step: str, exc: BaseException, *, model: object = None) -> None:
    lines = [f"paperlint [{step}] API error: {type(exc).__name__}: {exc}"]
    if model is not None:
        lines.append(f"paperlint [{step}] model: {model}")
    code = getattr(exc, "status_code", None)
    if code is not None:
        lines.append(f"paperlint [{step}] HTTP status: {code}")
    body = getattr(exc, "body", None)
    if isinstance(body, str) and body.strip():
        b = body.strip()[:2000]
        lines.append(f"paperlint [{step}] error body: {b}")
    for line in lines:
        print(line, file=sys.stderr)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Evidence:
    location: str
    quote: str
    verified: bool = False


@dataclass
class Finding:
    number: int
    title: str
    category: str
    defect: str
    correction: str
    axiom: str
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class GatedFinding:
    finding: Finding
    verdict: str  # PASS | REJECT | REFER
    reason: str


@dataclass
class PaperMeta:
    paper: str
    title: str
    authors: list[str]
    target_group: str
    paper_type: str
    abstract: str
    source_file: str
    run_timestamp: str
    model: str


# ---------------------------------------------------------------------------
# API call helpers
# ---------------------------------------------------------------------------

def _call_with_retry(client: openai.OpenAI, step: str, **kwargs):
    model = kwargs.get("model", "?")
    for attempt in range(MAX_RETRIES):
        try:
            return client.chat.completions.create(**kwargs)
        except openai.RateLimitError as e:
            if attempt == MAX_RETRIES - 1:
                _log_error(step, e, model=model)
                raise
            wait = RETRY_BASE_DELAY * (attempt + 1)
            print(f"  [{step}] Rate limited. Waiting {wait}s ({attempt + 1}/{MAX_RETRIES})...")
            time.sleep(wait)
        except Exception as e:
            _log_error(step, e, model=model)
            raise


def _log_usage(step: str, response, budget: int):
    u = response.usage
    prompt_tok = u.prompt_tokens if u else 0
    completion_tok = u.completion_tokens if u else 0
    total_tok = u.total_tokens if u else 0
    print(f"\n  [{step}] tokens — prompt: {prompt_tok} | completion: {completion_tok} "
          f"| total: {total_tok} | thinking_budget: {budget}")


def _extract_text(response) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""
    msg = choices[0].message
    return msg.content if msg and msg.content else ""


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw[raw.index("\n") + 1:] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:raw.rfind("```")].strip()
    return raw


def _parse_json(raw: str, step: str = "") -> dict | list:
    stripped = _strip_fences(raw)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as e:
        label = step or "JSON"
        print(f"paperlint [{label}] JSONDecodeError: {e}", file=sys.stderr)
        preview = stripped[:800]
        print(f"paperlint [{label}] raw: {repr(preview)}", file=sys.stderr)
        raise


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def step_metadata(paper_path: Path, client: openai.OpenAI) -> tuple[str, PaperMeta]:
    """Step 0: Extract metadata via Sonnet."""
    print("\n--- Step 0: Metadata ---")

    paper_number = paper_path.stem.upper()

    try:
        clean_text = extract_text(str(paper_path))
    except Exception as e:
        print(f"  Text extraction failed: {e}")
        if paper_path.suffix.lower() != ".pdf":
            clean_text = paper_path.read_text(encoding="utf-8")[:15000]
        else:
            clean_text = f"[Document: {paper_number}]"

    meta_prompt = (
        "Read this WG21 paper and return ONLY a JSON object with these fields:\n\n"
        '{"title": "...", "authors": ["..."], "audience": "...", '
        '"paper_type": "wording or proposal or directional", '
        '"abstract": "2-3 sentence summary of what this paper proposes."}\n\n'
        "Return ONLY the JSON."
    )

    title = "Unknown"
    authors: list[str] = []
    audience = "Unknown"
    paper_type = "wording"
    abstract = ""

    for attempt in range(1, 4):
        try:
            response = client.chat.completions.create(
                model=OPENROUTER_SONNET,
                max_tokens=512,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": f"{meta_prompt}\n\n{clean_text}"}],
            )
            raw = _extract_text(response).strip()
            if not raw:
                raise ValueError("Empty response")
            parsed = json.loads(_strip_fences(raw))
            title = parsed.get("title", "Unknown")
            authors = parsed.get("authors", [])
            if isinstance(authors, str):
                authors = [a.strip() for a in authors.split(",")]
            audience = parsed.get("audience", "Unknown")
            paper_type = parsed.get("paper_type", "wording")
            abstract = parsed.get("abstract", "")
            if title != "Unknown" and audience != "Unknown":
                break
        except Exception as e:
            print(f"  Metadata attempt {attempt}/3 failed: {e}")
            if attempt < 3:
                time.sleep(2)

    meta = PaperMeta(
        paper=paper_number, title=title, authors=authors,
        target_group=audience, paper_type=paper_type, abstract=abstract,
        source_file=str(paper_path),
        run_timestamp=datetime.now(timezone.utc).isoformat(),
        model=OPENROUTER_MODEL,
    )

    print(f"  Paper: {meta.paper} — {meta.title}")
    print(f"  Authors: {', '.join(meta.authors)}")
    print(f"  Target: {meta.target_group} | Type: {meta.paper_type}")
    return clean_text, meta


def step_discovery(client: openai.OpenAI, clean_text: str, meta: PaperMeta) -> list[Finding]:
    """Step 1: Discovery — find defects, output structured JSON with evidence."""
    print("\n--- Step 1: Discovery (JSON mode + thinking) ---")

    rubric_text = RUBRIC_PATH.read_text(encoding="utf-8")
    skill_text = (PROMPTS_DIR / "1-discovery.md").read_text(encoding="utf-8")

    json_schema = (
        "\n\n## Output Format\n\n"
        "Return ONLY a JSON object with this structure:\n"
        '{"findings": [\n'
        '  {\n'
        '    "number": 1,\n'
        '    "title": "short title",\n'
        '    "category": "rubric code e.g. 1.2",\n'
        '    "defect": "what is wrong — one sentence",\n'
        '    "correction": "what it should say — one sentence",\n'
        '    "axiom": "ground truth source",\n'
        '    "evidence": [\n'
        '      {"location": "§X.Y or section name", "quote": "exact text from the paper"}\n'
        '    ]\n'
        '  }\n'
        ']}\n\n'
        "Each evidence quote must be EXACT text from the paper — copy precisely, "
        "character for character. Do not paraphrase. Do not combine multiple passages "
        "into one quote. Use separate evidence entries for each passage.\n\n"
        "If no findings, return {\"findings\": []}.\n"
        "Return ONLY the JSON."
    )

    system_prompt = f"{skill_text}\n\n---\n\n# Evaluation Rubric\n\n{rubric_text}{json_schema}"

    user_content = (
        f"<paper title=\"{meta.paper} — {meta.title}\" "
        f"target_group=\"{meta.target_group}\" "
        f"authors=\"{', '.join(meta.authors)}\">\n"
        f"{clean_text}\n"
        f"</paper>\n\n"
        f"Analyze this paper for objective defects per the rubric."
    )

    parsed = None
    for attempt in range(2):
        response = _call_with_retry(
            client, "Discovery",
            model=OPENROUTER_MODEL,
            max_tokens=MAX_TOKENS["discovery"],
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            extra_body={
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": THINKING_BUDGET["discovery"],
                },
            },
        )

        _log_usage("Discovery", response, THINKING_BUDGET["discovery"])

        raw = _extract_text(response)
        try:
            parsed = _parse_json(raw, "Discovery")
            break
        except json.JSONDecodeError:
            if attempt == 0:
                print("  Retrying Discovery (JSON parse failed, attempt 2)...")
                user_content = (
                    f"<paper title=\"{meta.paper} — {meta.title}\" "
                    f"target_group=\"{meta.target_group}\" "
                    f"authors=\"{', '.join(meta.authors)}\">\n"
                    f"{clean_text}\n"
                    f"</paper>\n\n"
                    f"Analyze this paper for objective defects per the rubric.\n\n"
                    f"IMPORTANT: Return ONLY a valid JSON object. No markdown. No explanation."
                )
            else:
                raise

    raw_findings = parsed.get("findings", [])

    findings: list[Finding] = []
    for rf in raw_findings:
        evidence = [
            Evidence(location=e.get("location", ""), quote=e.get("quote", ""))
            for e in rf.get("evidence", [])
        ]
        findings.append(Finding(
            number=rf.get("number", 0),
            title=rf.get("title", ""),
            category=rf.get("category", ""),
            defect=rf.get("defect", ""),
            correction=rf.get("correction", ""),
            axiom=rf.get("axiom", ""),
            evidence=evidence,
        ))

    print(f"  Findings: {len(findings)}")
    for f in findings:
        print(f"    #{f.number}: {f.title[:60]} ({len(f.evidence)} evidence)")

    return findings


def step_verify_quotes(findings: list[Finding], source_text: str) -> list[Finding]:
    """Step 1b: Programmatic quote verification — reject findings with unverifiable evidence."""
    print("\n--- Step 1b: Quote Verification ---")

    source_norm = " ".join(source_text.split())
    verified_findings: list[Finding] = []

    for f in findings:
        all_verified = True
        for ev in f.evidence:
            exact = ev.quote in source_text
            if not exact:
                norm = " ".join(ev.quote.split()) in source_norm
            else:
                norm = False
            ev.verified = exact or norm
            status = "EXACT" if exact else ("NORM" if norm else "MISS")
            if not ev.verified:
                all_verified = False
            print(f"    #{f.number} [{status}] \"{ev.quote[:60]}\"")

        if any(ev.verified for ev in f.evidence):
            verified_findings.append(f)
        else:
            print(f"    #{f.number} DROPPED — no verifiable evidence")

    dropped = len(findings) - len(verified_findings)
    if dropped:
        print(f"  Dropped {dropped} finding(s) with no verifiable evidence")
    print(f"  Verified: {len(verified_findings)}/{len(findings)}")

    return verified_findings


def _format_findings_for_gate(findings: list[Finding]) -> str:
    lines = ["# Candidate Findings for Verification\n"]
    for f in findings:
        lines.append(f"## Finding #{f.number}: {f.title}")
        lines.append(f"- **Category:** {f.category}")
        for ev in f.evidence:
            lines.append(f"- **Location:** {ev.location}")
            lines.append(f'- **Quoted text:** "{ev.quote}"')
        lines.append(f"- **Defect:** {f.defect}")
        lines.append(f"- **Correction:** {f.correction}")
        lines.append(f"- **Axiom:** {f.axiom}")
        lines.append("")
    return "\n".join(lines)


def _format_findings_for_eval(meta: PaperMeta, passed: list[GatedFinding]) -> str:
    lines = [
        "# Paper Metadata\n",
        f"- **Paper:** {meta.paper}",
        f"- **Title:** {meta.title}",
        f"- **Authors:** {', '.join(meta.authors)}",
        f"- **Target group:** {meta.target_group}",
        "",
        f"# Gated Findings ({len(passed)} items)\n",
    ]
    for g in passed:
        f = g.finding
        lines.append(f"## Finding #{f.number}: {f.title}")
        lines.append(f"- **Category:** {f.category}")
        for ev in f.evidence:
            lines.append(f"- **Location:** {ev.location}")
            lines.append(f'- **Quoted text:** "{ev.quote}"')
        lines.append(f"- **Defect:** {f.defect}")
        lines.append(f"- **Correction:** {f.correction}")
        lines.append("")
    return "\n".join(lines)


def step_gate(client: openai.OpenAI, paper_text: str,
              meta: PaperMeta, findings: list[Finding]) -> list[GatedFinding]:
    """Step 2: Verification Gate."""
    print("\n--- Step 2: Gate ---")

    if not findings:
        print("  No findings to gate.")
        return []

    system_prompt = (PROMPTS_DIR / "2-verification-gate.md").read_text(encoding="utf-8")
    findings_text = _format_findings_for_gate(findings)

    user_content = (
        f"<paper title=\"{meta.paper} — {meta.title}\">\n"
        f"{paper_text}\n"
        f"</paper>\n\n"
        f"{findings_text}"
    )

    json_instruction = (
        "\n\n## Output Format\n\n"
        "Return ONLY a JSON object:\n"
        '{"verdicts": [\n'
        '  {"finding_number": 1, "verdict": "PASS", "reason": "..."}\n'
        ']}\n'
        "verdict must be PASS, REJECT, or REFER.\n"
        "Return ONLY the JSON."
    )

    response = _call_with_retry(
        client, "Gate",
        model=OPENROUTER_MODEL,
        max_tokens=MAX_TOKENS["gate"],
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt + json_instruction},
            {"role": "user", "content": user_content},
        ],
        extra_body={
            "thinking": {
                "type": "enabled",
                "budget_tokens": THINKING_BUDGET["gate"],
            },
        },
    )

    _log_usage("Gate", response, THINKING_BUDGET["gate"])

    raw = _extract_text(response)
    if not raw.strip():
        raise RuntimeError(f"paperlint [Gate] Empty response for {meta.paper}")

    parsed = _parse_json(raw, f"Gate paper={meta.paper}")
    verdicts = parsed.get("verdicts", [])

    gated: list[GatedFinding] = []
    verdict_map = {v["finding_number"]: v for v in verdicts}
    for f in findings:
        v = verdict_map.get(f.number, {"verdict": "REFER", "reason": "No verdict returned"})
        gated.append(GatedFinding(
            finding=f,
            verdict=v.get("verdict", "REFER").upper(),
            reason=v.get("reason", ""),
        ))

    passed = [g for g in gated if g.verdict == "PASS"]
    rejected = [g for g in gated if g.verdict == "REJECT"]
    referred = [g for g in gated if g.verdict == "REFER"]
    print(f"  PASS: {len(passed)} | REJECT: {len(rejected)} | REFER: {len(referred)}")
    for g in gated:
        print(f"    #{g.finding.number}: {g.verdict} — {g.reason[:80]}")

    return gated


def step_summary_writer(client: openai.OpenAI, meta: PaperMeta,
                        n_findings: int) -> str:
    """Step 3: Write the evaluation summary. Findings pass through from Discovery untouched."""
    print("\n--- Step 3: Summary ---")

    if n_findings == 0:
        summary = f"No objective problems found in {meta.paper} — {meta.title}."
        print(f"  Clean paper: {summary}")
        return summary

    system_prompt = (PROMPTS_DIR / "3-evaluation-writer.md").read_text(encoding="utf-8")

    json_instruction = (
        "\n\n## Output Format\n\n"
        "Return ONLY a JSON object:\n"
        '{"summary": "2-3 sentence summary of what the paper proposes and what was found. Plain text."}\n\n'
        "Write ONLY the summary. Findings are assembled separately.\n"
        "Return ONLY the JSON."
    )

    user_content = (
        f"Paper: {meta.paper} — {meta.title}\n"
        f"Authors: {', '.join(meta.authors)}\n"
        f"Audience: {meta.target_group}\n"
        f"Type: {meta.paper_type}\n"
        f"Abstract: {meta.abstract}\n\n"
        f"Number of findings that passed verification: {n_findings}\n\n"
        f"Write a 2-3 sentence summary of what this paper proposes. "
        f"State what it does neutrally — do not use the author's persuasive framing."
    )

    response = _call_with_retry(
        client, "Summary",
        model=OPENROUTER_SONNET,
        max_tokens=512,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt + json_instruction},
            {"role": "user", "content": user_content},
        ],
    )

    raw = _extract_text(response)
    try:
        parsed = json.loads(_strip_fences(raw))
        summary = parsed.get("summary", f"Evaluation of {meta.paper}.")
    except json.JSONDecodeError:
        summary = f"Evaluation of {meta.paper} — {meta.title}."

    print(f"  Summary: {summary[:100]}...")
    return summary


# ---------------------------------------------------------------------------
# Paper fetching
# ---------------------------------------------------------------------------

OPEN_STD_BASE = "https://www.open-std.org/jtc1/sc22/wg21/docs/papers"


def _looks_like_doc_id(paper_ref: str) -> bool:
    u = paper_ref.strip().upper()
    if not u or "/" in u or "\\" in u:
        return False
    return len(u) >= 2 and u[0] in ("P", "N") and u[1].isdigit()


def fetch_paper(paper_id: str, cache_dir: Path | None = None) -> Path:
    """Fetch a WG21 document by ID. Returns local file path."""
    import urllib.request
    import urllib.error

    if cache_dir is None:
        cache_dir = Path.cwd() / ".paperlint_cache"
    paper_lower = paper_id.lower()
    cache_dir.mkdir(parents=True, exist_ok=True)

    for ext in [".html", ".pdf"]:
        local = cache_dir / f"{paper_lower}{ext}"
        if local.exists():
            print(f"  Found cached: {local}")
            return local

    for year in ["2026", "2025", "2024"]:
        for ext in [".html", ".pdf"]:
            url = f"{OPEN_STD_BASE}/{year}/{paper_lower}{ext}"
            local = cache_dir / f"{paper_lower}{ext}"
            try:
                print(f"  Trying: {url}")
                urllib.request.urlretrieve(url, str(local))
                print(f"  Downloaded: {local}")
                return local
            except urllib.error.HTTPError:
                if local.exists():
                    local.unlink()

    raise FileNotFoundError(f"Could not find {paper_id} on open-std.org")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_paper_eval(
    paper_ref: str,
    *,
    output_dir: Path,
) -> dict:
    """Evaluate one paper. Write evaluation.json to output_dir."""
    paper_path = Path(paper_ref)
    if paper_path.exists():
        pass
    elif _looks_like_doc_id(paper_ref):
        print(f"Fetching {paper_ref}...")
        paper_path = fetch_paper(paper_ref.upper())
    else:
        raise FileNotFoundError(paper_ref)

    ensure_api_keys()

    client = openai.OpenAI(
        base_url=resolve_openrouter_base_url(),
        api_key=os.environ["OPENROUTER_API_KEY"],
    )

    paper_id = paper_path.stem
    paper_output_dir = output_dir / paper_id
    paper_output_dir.mkdir(parents=True, exist_ok=True)

    # Step 0: Metadata
    clean_text, meta = step_metadata(paper_path, client)
    if meta.title == "Unknown":
        print(f"\n  SKIPPED: {meta.paper} — metadata extraction failed.")
        return {}

    meta_path = paper_output_dir / "meta.json"
    meta_path.write_text(json.dumps(asdict(meta), indent=2), encoding="utf-8")

    # Step 1: Discovery
    findings = step_discovery(client, clean_text, meta)

    findings_path = paper_output_dir / "1-findings.json"
    findings_path.write_text(
        json.dumps([asdict(f) for f in findings], indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(f"  Written: {findings_path}")

    # Step 1b: Quote verification
    findings = step_verify_quotes(findings, clean_text)

    # Step 2: Gate
    gated = step_gate(client, clean_text, meta, findings)

    gate_path = paper_output_dir / "2-gate.json"
    gate_path.write_text(json.dumps(
        [{"finding_number": g.finding.number, "verdict": g.verdict, "reason": g.reason}
         for g in gated], indent=2), encoding="utf-8")

    # Step 3: Summary
    passed = [g for g in gated if g.verdict == "PASS"]
    summary = step_summary_writer(client, meta, len(passed))

    # Step 4: Assembly — findings pass through from Discovery, unmodified
    # References are numbered per quote, not per finding.
    # Build references first, then attach reference numbers to findings.
    references = []
    ref_counter = 1
    output_findings = []

    for gf in passed:
        f = gf.finding
        finding_refs = []
        for ev in f.evidence:
            if ev.verified:
                references.append({
                    "number": ref_counter,
                    "location": ev.location,
                    "quote": ev.quote,
                    "verified": True,
                })
                finding_refs.append(ref_counter)
                ref_counter += 1
        output_findings.append({
            "location": f.evidence[0].location if f.evidence else "",
            "description": f.defect,
            "category": f.category,
            "correction": f.correction,
            "references": finding_refs,
        })

    eval_json = {
        "schema_version": SCHEMA_VERSION,
        "paperlint_sha": _git_sha(),
        "prompt_hash": _prompt_hash(),
        "paper": meta.paper,
        "title": meta.title,
        "authors": meta.authors,
        "audience": meta.target_group,
        "paper_type": meta.paper_type,
        "abstract": meta.abstract,
        "generated": meta.run_timestamp,
        "model": meta.model,
        "findings_discovered": len(findings),
        "findings_passed": len(passed),
        "findings_rejected": len([g for g in gated if g.verdict == "REJECT"]),
        "summary": summary,
        "findings": output_findings,
        "references": references,
    }

    json_path = paper_output_dir / "evaluation.json"
    json_path.write_text(json.dumps(eval_json, indent=2, ensure_ascii=False), encoding="utf-8")

    flat_path = output_dir / f"{meta.paper}.json"
    flat_path.write_text(json.dumps(eval_json, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'=' * 60}")
    print(f"Pipeline complete. Deliverable: {flat_path}")
    print(f"{'=' * 60}")

    return eval_json
