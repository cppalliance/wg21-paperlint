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
from paperlint.suppress import step_suppress_known_fps

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PKG_ROOT = Path(__file__).resolve().parent

OPENROUTER_MODEL = "anthropic/claude-opus-4.6"
OPENROUTER_SONNET = "anthropic/claude-sonnet-4.6"

SCHEMA_VERSION = "1"

THINKING_BUDGET = {
    "discovery": 128_000,
    "gate": 128_000,
    "summary": 8_000,
}

MAX_TOKENS = {
    "discovery": 128_000,
    "gate": 128_000,
    "summary": 4_096,
}

PROMPTS_DIR = _PKG_ROOT / "prompts"
RUBRIC_PATH = _PKG_ROOT / "rubric.md"

# Rubric questions currently in scope. Each entry has an id and the literal question text.
# Questions are added one at a time as each is calibrated.
QUESTIONS_IN_SCOPE: list[dict] = [
    {
        "id": "Q1",
        "question": "Does the paper show code of the feature it is proposing?",
    },
]

# Base URL for the extracted paper.md files on GitHub. Used to build click-through
# links from each review.md back to the source markdown the LLM read.
# Update when the branch is renamed or the output directory changes.
PAPER_MD_BASE_URL = "https://github.com/cppalliance/paperlint/blob/feature/sd4-rubric-v2/output-sd4-v4"

MAX_RETRIES = 3
RETRY_BASE_DELAY = 10


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
    extracted_char_start: int | None = None
    extracted_char_end: int | None = None


@dataclass
class Finding:
    """A rubric-question result for a paper: applicability + (if applicable) answered + evidence."""
    question: str  # e.g. "Q1"
    applicable: bool = True
    answered: bool = False  # meaningful only when applicable
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
        except (openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError) as e:
            if attempt == MAX_RETRIES - 1:
                _log_error(step, e, model=model)
                raise
            wait = RETRY_BASE_DELAY * (attempt + 1)
            label = type(e).__name__
            print(f"  [{step}] {label}. Waiting {wait}s ({attempt + 1}/{MAX_RETRIES})...")
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
    decoder = json.JSONDecoder()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    if start >= 0:
        try:
            result, _ = decoder.raw_decode(stripped, start)
            return result
        except json.JSONDecodeError:
            pass

    try:
        result, _ = decoder.raw_decode(stripped)
        return result
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
        '{"title": "...", "authors": ["..."], "audience": "...", "paper_type": "..."}\n\n'
        "paper_type must be exactly one of the following, chosen by what the paper primarily does:\n\n"
        "- \"proposal\": proposes a design addition or change — a new feature, API, function, "
        "class, concept, or language capability. Papers that introduce new `std::` entities "
        "(functions, types, concepts), new syntax, or new semantics are proposals, even when "
        "they include standardese wording. If the paper's purpose is to add something new to "
        "C++, it is a proposal.\n"
        "- \"wording\": clarifies or corrects existing standardese without adding new design "
        "content. Editorial fixes, defect reports (DRs), or specification clarifications for "
        "features that already exist in the standard.\n"
        "- \"directional\": sets direction or priorities for WG21 without proposing a specific "
        "feature (e.g., committee strategy, priority lists, roadmap papers).\n"
        "- \"white-paper\": exploratory analysis on a topic not yet in proposal form.\n"
        "- \"informational\": reports, analyses, or content that does not propose changes.\n\n"
        "When in doubt between proposal and wording, pick proposal if the paper adds new "
        "entities or capabilities, and wording only if it strictly corrects existing text.\n\n"
        "Return ONLY the JSON."
    )

    title = "Unknown"
    authors: list[str] = []
    audience = "Unknown"
    paper_type = "wording"

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
            if title != "Unknown" and audience != "Unknown":
                break
        except Exception as e:
            print(f"  Metadata attempt {attempt}/3 failed: {e}")
            if attempt < 3:
                time.sleep(2)

    meta = PaperMeta(
        paper=paper_number, title=title, authors=authors,
        target_group=audience, paper_type=paper_type,
        source_file=str(paper_path),
        run_timestamp=datetime.now(timezone.utc).isoformat(),
        model=OPENROUTER_MODEL,
    )

    print(f"  Paper: {meta.paper} — {meta.title}")
    print(f"  Authors: {', '.join(meta.authors)}")
    print(f"  Target: {meta.target_group} | Type: {meta.paper_type}")
    return clean_text, meta


def step_discovery(client: openai.OpenAI, clean_text: str, meta: PaperMeta) -> list[Finding]:
    """Step 1: Discovery — for each in-scope question, return applicability + (if applicable) answered + evidence."""
    print("\n--- Step 1: Discovery (JSON mode + thinking) ---")

    rubric_text = RUBRIC_PATH.read_text(encoding="utf-8")
    skill_text = (PROMPTS_DIR / "1-discovery.md").read_text(encoding="utf-8")

    question_ids = ", ".join(q["id"] for q in QUESTIONS_IN_SCOPE)

    json_schema = (
        "\n\n## Output Format\n\n"
        "Return ONLY a JSON object with this structure. For each in-scope question "
        f"({question_ids}), return one result with one of three shapes:\n\n"
        "Not applicable:\n"
        '  {"question": "Q1", "applicable": false}\n\n'
        "Applicable but not answered:\n"
        '  {"question": "Q1", "applicable": true, "answered": false}\n\n'
        "Applicable and answered:\n"
        '  {"question": "Q1", "applicable": true, "answered": true,\n'
        '   "evidence": [{"location": "§X.Y or section name", "quote": "exact text from the paper"}]}\n\n'
        "Wrap the results in an object:\n"
        '  {"results": [ ... ]}\n\n'
        "Pick ONE evidence entry per answered question — the single strongest passage. "
        "The quote must be EXACT text from the paper, copied character for character. "
        "Keep it minimal — a handful of lines. Do not include multiple evidence entries.\n\n"
        "Return ONLY the JSON."
    )

    system_prompt = f"{skill_text}\n\n---\n\n# Evaluation Rubric\n\n{rubric_text}{json_schema}"

    user_content = (
        f"<paper title=\"{meta.paper} — {meta.title}\" "
        f"target_group=\"{meta.target_group}\" "
        f"authors=\"{', '.join(meta.authors)}\">\n"
        f"{clean_text}\n"
        f"</paper>\n\n"
        f"Evaluate each in-scope question against this paper per the rubric.\n\n"
        f"IMPORTANT: Return ONLY a valid JSON object. No markdown. No explanation."
    )

    parsed = None
    for attempt in range(3):
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
            if attempt < 2:
                print(
                    f"  Retrying Discovery (JSON parse failed, attempt {attempt + 2})..."
                )
            else:
                raise

    raw_results = parsed.get("results", [])

    findings: list[Finding] = []
    for rr in raw_results:
        evidence = [
            Evidence(location=e.get("location", ""), quote=e.get("quote", ""))
            for e in rr.get("evidence", [])
        ]
        findings.append(Finding(
            question=rr.get("question", ""),
            applicable=bool(rr.get("applicable", True)),
            answered=bool(rr.get("answered", False)),
            evidence=evidence,
        ))

    print(f"  Results: {len(findings)}")
    for f in findings:
        if not f.applicable:
            state = "NOT APPLICABLE"
        elif f.answered:
            state = f"ANSWERED ({len(f.evidence)} evidence)"
        else:
            state = "APPLICABLE BUT NOT ANSWERED"
        print(f"    [{f.question}] {state}")

    return findings


def step_verify_quotes(findings: list[Finding], source_text: str) -> list[Finding]:
    """Step 1b: Programmatic quote verification — reject findings with unverifiable evidence."""
    print("\n--- Step 1b: Quote Verification ---")

    source_norm = " ".join(source_text.split())
    verified_findings: list[Finding] = []

    for f in findings:
        all_verified = True
        for ev in f.evidence:
            idx = source_text.find(ev.quote)
            if idx >= 0:
                ev.verified = True
                ev.extracted_char_start = idx
                ev.extracted_char_end = idx + len(ev.quote)
                status = "EXACT"
            else:
                norm_quote = " ".join(ev.quote.split())
                norm_idx = source_norm.find(norm_quote)
                if norm_idx >= 0:
                    ev.verified = True
                    # Map normalized position back to original text
                    char_count = 0
                    orig_start = 0
                    for i, ch in enumerate(source_text):
                        if char_count == norm_idx:
                            orig_start = i
                            break
                        if not (ch in ' \t\n\r' and (i == 0 or source_text[i-1] in ' \t\n\r')):
                            char_count += 1
                    ev.extracted_char_start = orig_start
                    ev.extracted_char_end = min(orig_start + len(ev.quote) + 50, len(source_text))
                    # Tighten end by searching for the quote's last word near the estimated end
                    last_words = ev.quote.split()[-2:] if len(ev.quote.split()) >= 2 else ev.quote.split()
                    tail = " ".join(last_words)
                    tail_idx = source_text.find(tail, orig_start)
                    if tail_idx >= 0:
                        ev.extracted_char_end = tail_idx + len(tail)
                    status = "NORM"
                else:
                    ev.verified = False
                    status = "MISS"
            if not ev.verified:
                all_verified = False
            print(f"    [{f.question}] [{status}] \"{ev.quote[:60]}\"")

        # Keep findings with no evidence (not-applicable or applicable-not-answered)
        # or with all evidence verified. Downgrade findings whose cited evidence does
        # not match the paper: the applicability stands, but answered flips to false
        # and evidence is cleared.
        if not f.evidence:
            verified_findings.append(f)
        elif all(ev.verified for ev in f.evidence):
            verified_findings.append(f)
        else:
            unverified = sum(1 for ev in f.evidence if not ev.verified)
            print(f"    [{f.question}] DOWNGRADED — {unverified} unverifiable quote(s); answered→false")
            f.answered = False
            f.evidence = []
            verified_findings.append(f)

    dropped = len(findings) - len(verified_findings)
    if dropped:
        print(f"  Dropped {dropped} finding(s) with no verifiable evidence")
    print(f"  Verified: {len(verified_findings)}/{len(findings)}")

    return verified_findings


def _format_findings_for_gate(findings: list[Finding]) -> str:
    """Format discovery results as markdown for the gate to verify."""
    lines = ["# Discovery Results for Verification\n"]
    for f in findings:
        lines.append(f"## {f.question}")
        if not f.applicable:
            lines.append("- **State:** not applicable")
        elif not f.answered:
            lines.append("- **State:** applicable but not answered")
        else:
            lines.append("- **State:** applicable and answered")
            for ev in f.evidence:
                lines.append(f"- **Evidence location:** {ev.location}")
                lines.append(f'- **Evidence quote:** "{ev.quote}"')
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
        "Return ONLY a JSON object with one verdict per discovery result:\n"
        '{"verdicts": [\n'
        '  {"question": "Q1", "verdict": "PASS", "reason": "...", "judgment": false}\n'
        ']}\n\n'
        "Each verdict is keyed by the question ID.\n"
        "verdict must be PASS, REJECT, or REFER.\n"
        "judgment: true if reaching this verdict required judgment beyond the rubric's "
        "applicability and evidence rules; false if those rules applied directly.\n"
        "Return ONLY the JSON."
    )

    parsed = None
    for attempt in range(3):
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
            if attempt == 0:
                print("  Retrying Gate (empty response, attempt 2)...")
                continue
            raise RuntimeError(f"paperlint [Gate] Empty response for {meta.paper}")

        try:
            parsed = _parse_json(raw, f"Gate paper={meta.paper}")
            break
        except json.JSONDecodeError:
            if attempt < 2:
                print(f"  Retrying Gate (JSON parse failed, attempt {attempt + 2})...")
            else:
                raise

    verdicts = parsed.get("verdicts", [])

    gated: list[GatedFinding] = []
    verdict_map = {v.get("question", ""): v for v in verdicts}
    judgment_rejections = 0
    for f in findings:
        v = verdict_map.get(f.question, {"verdict": "REFER", "reason": "No verdict returned"})
        verdict = v.get("verdict", "REFER").upper()
        reason = v.get("reason", "")
        used_judgment = v.get("judgment", False)
        if verdict == "PASS" and used_judgment:
            verdict = "REJECT"
            reason = f"Auto-rejected: gate reported judgment was required. Original: {reason}"
            judgment_rejections += 1
        gated.append(GatedFinding(
            finding=f,
            verdict=verdict,
            reason=reason,
        ))

    passed = [g for g in gated if g.verdict == "PASS"]
    rejected = [g for g in gated if g.verdict == "REJECT"]
    referred = [g for g in gated if g.verdict == "REFER"]
    print(f"  PASS: {len(passed)} | REJECT: {len(rejected)} | REFER: {len(referred)}")
    if judgment_rejections:
        print(f"  ({judgment_rejections} auto-rejected: PASS with judgment)")
    for g in gated:
        print(f"    [{g.finding.question}] {g.verdict} — {g.reason[:80]}")

    return gated


def compute_summary(applicable_count: int, answered_count: int) -> str:
    """Deterministic score-based summary. No LLM needed."""
    if applicable_count == 0:
        return "It looks like no questions apply to this paper."
    return f"Answered {answered_count} of {applicable_count} applicable questions."


# ---------------------------------------------------------------------------
# Paper fetching
# ---------------------------------------------------------------------------

OPEN_STD_BASE = "https://www.open-std.org/jtc1/sc22/wg21/docs/papers"


def _looks_like_doc_id(paper_ref: str) -> bool:
    u = paper_ref.strip().upper()
    if not u or "/" in u or "\\" in u:
        return False
    return len(u) >= 2 and u[0] in ("P", "N") and u[1].isdigit()


def fetch_paper(paper_id: str, cache_dir: Path | None = None, source_url: str = "") -> Path:
    """Fetch a WG21 document by ID. Returns local file path.

    When *source_url* is provided (from the mailing index), it is used
    directly — no year/extension guessing.  Falls back to the legacy
    heuristic when source_url is empty (single-paper ``eval`` mode).
    """
    import urllib.request
    import urllib.error

    if cache_dir is None:
        cache_dir = Path.cwd() / ".paperlint_cache"
    paper_lower = paper_id.lower()
    cache_dir.mkdir(parents=True, exist_ok=True)

    if source_url:
        filename = source_url.rsplit("/", 1)[-1].lower()
        local = cache_dir / filename
        if local.exists():
            print(f"  Found cached: {local}")
            return local
        print(f"  Downloading: {source_url}")
        urllib.request.urlretrieve(source_url, str(local))
        print(f"  Downloaded: {local}")
        return local

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

def _write_eval_json(eval_json: dict, output_dir: Path, paper_id: str) -> None:
    """Write evaluation.json to the paper subdirectory."""
    paper_output_dir = output_dir / paper_id
    paper_output_dir.mkdir(parents=True, exist_ok=True)

    json_path = paper_output_dir / "evaluation.json"
    json_path.write_text(json.dumps(eval_json, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_review_md(eval_json: dict, output_dir: Path, paper_id: str) -> None:
    """Write a human-readable review.md alongside evaluation.json, per the Vinnie-approved template."""
    paper_output_dir = output_dir / paper_id
    paper_output_dir.mkdir(parents=True, exist_ok=True)

    refs_by_number = {r["number"]: r for r in eval_json.get("references", [])}
    title = eval_json.get("title", "")
    paper = eval_json.get("paper", paper_id)
    summary = eval_json.get("summary", "")
    applicable_answered = eval_json.get("applicable_answered", [])
    applicable_unanswered = eval_json.get("applicable_unanswered", [])
    not_applicable = eval_json.get("not_applicable", [])

    paper_link = f"{PAPER_MD_BASE_URL}/{paper}/paper.md"
    lines: list[str] = [
        f"# [{paper}]({paper_link}) - {title}",
        summary,
        "",
    ]

    # Applicable questions (answered first, then not answered), in the order of QUESTIONS_IN_SCOPE
    applicable_by_qid = {}
    for a in applicable_answered:
        applicable_by_qid[a["question"]] = ("answered", a)
    for a in applicable_unanswered:
        applicable_by_qid[a["question"]] = ("unanswered", a)

    for q in QUESTIONS_IN_SCOPE:
        state = applicable_by_qid.get(q["id"])
        if not state:
            continue
        status, entry = state
        lines.append(f"**{q['id']}. {q['question']}**")
        if status == "answered":
            for rn in entry.get("references", []):
                ref = refs_by_number.get(rn)
                if not ref:
                    continue
                quote = ref.get("quote", "").strip()
                if not quote:
                    continue
                # Preview cap: show at most 5 lines. Full quote stays in evaluation.json.
                quote_lines = quote.splitlines()
                truncated = len(quote_lines) > 5
                shown = quote_lines[:5]
                quoted = "\n".join(f"> {ln}" for ln in shown)
                lines.append(quoted)
                if truncated:
                    lines.append("> …")
        lines.append("")

    if not_applicable:
        # Only emit the "It looks like these questions don't apply" header when there
        # are applicable questions above it; otherwise the top-level summary already
        # says everything and the bullet list suffices.
        if applicable_answered or applicable_unanswered:
            lines.append("It looks like these questions don't apply to this paper:")
        for entry in not_applicable:
            qid = entry["question"]
            qtext = entry.get("question_text") or next(
                (q["question"] for q in QUESTIONS_IN_SCOPE if q["id"] == qid), ""
            )
            lines.append(f"- **{qid}. {qtext}**")
        lines.append("")

    md_path = paper_output_dir / "review.md"
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


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
        "applicable_count": 0,
        "answered_count": 0,
        "summary": "",
        "applicable_answered": [],
        "applicable_unanswered": [],
        "not_applicable": [],
        "references": [],
    }


def run_paper_eval(
    paper_ref: str,
    *,
    output_dir: Path,
    source_url: str = "",
    mailing_meta: dict | None = None,
) -> dict:
    """Evaluate one paper. Always writes an evaluation.json, even on failure."""
    paper_id = paper_ref.strip().upper() if _looks_like_doc_id(paper_ref) else Path(paper_ref).stem.upper()

    # Fetch paper
    try:
        paper_path = Path(paper_ref)
        if paper_path.exists():
            pass
        elif _looks_like_doc_id(paper_ref):
            print(f"Fetching {paper_ref}...")
            paper_path = fetch_paper(paper_ref.upper(), source_url=source_url)
        else:
            raise FileNotFoundError(paper_ref)
    except Exception as e:
        print(f"  FETCH FAILED: {paper_id} — {e}")
        eval_json = _base_eval_json(source_url, paper_id, mailing_meta)
        eval_json["summary"] = "This paper could not be evaluated due to a document retrieval issue."
        _write_eval_json(eval_json, output_dir, paper_id)
        return eval_json

    ensure_api_keys()

    client = openai.OpenAI(
        base_url=resolve_openrouter_base_url(),
        api_key=os.environ["OPENROUTER_API_KEY"],
    )

    paper_output_dir = output_dir / paper_id
    paper_output_dir.mkdir(parents=True, exist_ok=True)

    # Step 0: Metadata
    clean_text, meta = step_metadata(paper_path, client)
    if meta.title == "Unknown":
        print(f"  METADATA FAILED: {paper_id}")
        eval_json = _base_eval_json(source_url, paper_id, mailing_meta)
        eval_json["summary"] = "This paper could not be evaluated due to a document processing issue."
        _write_eval_json(eval_json, output_dir, paper_id)
        return eval_json

    meta_path = paper_output_dir / "meta.json"
    meta_path.write_text(json.dumps(asdict(meta), indent=2), encoding="utf-8")

    # Persist extraction as paper.md — the ground truth for char offset references
    paper_md_path = paper_output_dir / "paper.md"
    paper_md_path.write_text(clean_text, encoding="utf-8")

    # No scope gate under the positive-verification model. Every paper runs through
    # discovery; non-proposal papers will simply not earn any points, which is the
    # intended baseline outcome, not a defect.

    # Step 1: Discovery → Quote verification → Gate
    try:
        findings = step_discovery(client, clean_text, meta)
        raw_discovered = len(findings)

        findings_path = paper_output_dir / "1-findings.json"
        findings_path.write_text(
            json.dumps([asdict(f) for f in findings], indent=2, ensure_ascii=False),
            encoding="utf-8")
        print(f"  Written: {findings_path}")

        findings = step_verify_quotes(findings, clean_text)

        gated = step_gate(client, clean_text, meta, findings)

        gate_path = paper_output_dir / "2-gate.json"
        gate_path.write_text(json.dumps(
            [{"question": g.finding.question, "verdict": g.verdict, "reason": g.reason}
             for g in gated], indent=2), encoding="utf-8")

    except Exception as e:
        print(f"  ANALYSIS FAILED: {paper_id} — {e}")
        eval_json = _base_eval_json(source_url, paper_id, mailing_meta)
        eval_json["pipeline_status"] = "partial"
        eval_json["title"] = meta.title
        eval_json["authors"] = meta.authors
        eval_json["audience"] = meta.target_group
        eval_json["paper_type"] = meta.paper_type
        eval_json["summary"] = "This paper could not be fully evaluated due to an analysis issue."
        _write_eval_json(eval_json, output_dir, paper_id)
        return eval_json

    # Step 2b: Known-FP suppression
    # v1's suppression targets extraction-artifact defects (intra-word spacing, TOC
    # layout, bracketed identifier wrap). These are orthogonal to SD-4 gap findings,
    # which are about content quality, not text rendering. Suppression is skipped
    # under the SD-4 rubric; if we later need extraction-artifact handling, it
    # should happen in the extractor layer, not post-gate.
    suppressed: list = []
    suppressed_path = paper_output_dir / "2c-suppressed.json"
    suppressed_path.write_text(
        json.dumps(suppressed, indent=2, ensure_ascii=False),
        encoding="utf-8")

    # Step 3: Assembly — bucket each gated result into applicable/answered/not-applicable
    # Only PASS verdicts count; REJECT or REFER collapses the question back to the safe
    # default (applicable with no answer).
    question_state: dict[str, dict] = {}
    for gf in gated:
        f = gf.finding
        if gf.verdict != "PASS":
            question_state[f.question] = {"applicable": True, "answered": False, "evidence": []}
            continue
        question_state[f.question] = {
            "applicable": f.applicable,
            "answered": f.applicable and f.answered,
            "evidence": f.evidence if (f.applicable and f.answered) else [],
        }

    # Fill in any in-scope questions the gate skipped (treat as applicable, not answered).
    for q in QUESTIONS_IN_SCOPE:
        question_state.setdefault(q["id"], {"applicable": True, "answered": False, "evidence": []})

    references: list[dict] = []
    ref_counter = 1
    applicable_answered: list[dict] = []
    applicable_unanswered: list[dict] = []
    not_applicable: list[dict] = []

    for q in QUESTIONS_IN_SCOPE:
        state = question_state[q["id"]]
        entry = {"question": q["id"], "question_text": q["question"]}
        if not state["applicable"]:
            not_applicable.append(entry)
            continue
        if not state["answered"]:
            applicable_unanswered.append(entry)
            continue
        # Applicable and answered: collect references
        finding_refs: list[int] = []
        for ev in state["evidence"]:
            if not ev.verified:
                continue
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
        entry["references"] = finding_refs
        applicable_answered.append(entry)

    applicable_count = len(applicable_answered) + len(applicable_unanswered)
    answered_count = len(applicable_answered)
    summary = compute_summary(applicable_count, answered_count)
    print(f"\n--- Summary ---\n  {summary}")

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
        "applicable_count": applicable_count,
        "answered_count": answered_count,
        "summary": summary,
        "applicable_answered": applicable_answered,
        "applicable_unanswered": applicable_unanswered,
        "not_applicable": not_applicable,
        "references": references,
    }

    _write_eval_json(eval_json, output_dir, paper_id)
    _write_review_md(eval_json, output_dir, paper_id)

    print(f"\n{'=' * 60}")
    print(f"Pipeline complete. Deliverable: {output_dir / paper_id}/evaluation.json + review.md")
    print(f"{'=' * 60}")

    return eval_json
