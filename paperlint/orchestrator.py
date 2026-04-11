#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Paperlint pipeline orchestrator.

Runs Discovery -> Extractor -> Gate -> Evaluation Writer on a single paper.
Discovery uses the Anthropic API (for Citations). All other steps route
through OpenRouter (OpenAI-compatible) to spread rate limits.
"""

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import openai

from paperlint.credentials import ensure_api_keys, resolve_openrouter_base_url
from paperlint.extract import extract_text

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PKG_ROOT = Path(__file__).resolve().parent

ANTHROPIC_MODEL = "claude-opus-4-6"
OPENROUTER_MODEL = "anthropic/claude-opus-4.6"
OPENROUTER_SONNET = "anthropic/claude-sonnet-4.6"

SCHEMA_VERSION = "1"

THINKING_BUDGET = {
    "discovery": 25_000,
    "gate": 5_000,
    "report_writer": 5_000,
}

MAX_TOKENS = {
    "discovery": 32_000,
    "gate": 8_192,
    "report_writer": 8_192,
}

PROMPTS_DIR = _PKG_ROOT / "prompts"
RUBRIC_PATH = _PKG_ROOT / "rubric.md"

MAX_RETRIES = 3
RETRY_BASE_DELAY = 65  # seconds — Anthropic Opus rate limit is per-minute
OR_RETRY_BASE_DELAY = 10  # OpenRouter rate limits reset faster


def _git_sha() -> str:
    """Return the short git SHA of the paperlint package, or 'unknown'."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=_PKG_ROOT,
            stderr=subprocess.DEVNULL,
        ).decode().strip()[:12]
    except Exception:
        return "unknown"


def _log_openai_compatible_error(step: str, exc: BaseException, *, model: object = None) -> None:
    """Print a single stderr block for CI logs."""
    lines: list[str] = [
        f"paperlint [{step}] API error: {type(exc).__name__}: {exc}",
    ]
    if model is not None:
        lines.append(f"paperlint [{step}] model: {model}")
    code = getattr(exc, "status_code", None)
    if code is not None:
        lines.append(f"paperlint [{step}] HTTP status: {code}")
    body = getattr(exc, "body", None)
    if isinstance(body, str) and body.strip():
        b = body.strip()
        if len(b) > 2000:
            b = b[:2000] + "...(truncated)"
        lines.append(f"paperlint [{step}] error body: {b}")
    elif body is not None:
        lines.append(f"paperlint [{step}] error body: {body!r}")
    resp = getattr(exc, "response", None)
    if resp is not None and not body:
        try:
            txt = getattr(resp, "text", None)
        except Exception:
            txt = None
        if txt and str(txt).strip():
            t = str(txt).strip()
            if len(t) > 2000:
                t = t[:2000] + "...(truncated)"
            lines.append(f"paperlint [{step}] response text: {t}")
    for line in lines:
        print(line, file=sys.stderr)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Citation:
    cited_text: str
    document_index: int
    document_title: str
    start_char_index: int
    end_char_index: int


@dataclass
class Finding:
    number: int
    title: str
    category: str
    location: str
    quoted_text: str
    defect: str
    correction: str
    axiom: str
    citations: list[Citation] = field(default_factory=list)


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
# API call helpers with retry
# ---------------------------------------------------------------------------

def anthropic_call_with_retry(client: anthropic.Anthropic, step: str, **kwargs):
    """Anthropic API call with retry on rate limit errors."""
    for attempt in range(MAX_RETRIES):
        try:
            return client.messages.create(**kwargs)
        except anthropic.RateLimitError as e:
            if attempt == MAX_RETRIES - 1:
                model = kwargs.get("model", "?")
                print(f"paperlint [{step}] Anthropic rate limit retries exhausted.", file=sys.stderr)
                _log_openai_compatible_error(step, e, model=model)
                raise
            wait = RETRY_BASE_DELAY * (attempt + 1)
            print(f"  [{step}] Anthropic rate limited. Waiting {wait}s "
                  f"({attempt + 1}/{MAX_RETRIES})...")
            time.sleep(wait)
        except Exception as e:
            model = kwargs.get("model", "?")
            _log_openai_compatible_error(step, e, model=model)
            raise


def openrouter_call_with_retry(client: openai.OpenAI, step: str, **kwargs):
    """OpenRouter API call with retry on rate limit errors."""
    model = kwargs.get("model", "?")
    base_url = getattr(client, "base_url", None)
    for attempt in range(MAX_RETRIES):
        try:
            return client.chat.completions.create(**kwargs)
        except openai.RateLimitError as e:
            if attempt == MAX_RETRIES - 1:
                if base_url is not None:
                    print(f"paperlint [{step}] base_url: {base_url}", file=sys.stderr)
                print(f"paperlint [{step}] OpenRouter rate limit retries exhausted.", file=sys.stderr)
                _log_openai_compatible_error(step, e, model=model)
                raise
            wait = OR_RETRY_BASE_DELAY * (attempt + 1)
            print(f"  [{step}] OpenRouter rate limited. Waiting {wait}s "
                  f"({attempt + 1}/{MAX_RETRIES})...")
            time.sleep(wait)
        except Exception as e:
            if base_url is not None:
                print(f"paperlint [{step}] base_url: {base_url}", file=sys.stderr)
            _log_openai_compatible_error(step, e, model=model)
            raise


def log_usage_anthropic(step: str, response, budget: int):
    """Log token usage for an Anthropic API call."""
    u = response.usage
    input_tok = u.input_tokens
    output_tok = u.output_tokens
    cache_creation = getattr(u, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(u, "cache_read_input_tokens", 0) or 0

    thinking_tok = 0
    for block in response.content:
        if block.type == "thinking":
            thinking_tok += len(block.thinking)

    api_thinking = getattr(u, "thinking_tokens", None)
    thinking_display = api_thinking if api_thinking is not None else f"~{thinking_tok} chars"

    print(f"\n  [{step}] (Anthropic) tokens — input: {input_tok} | output: {output_tok} "
          f"| thinking: {thinking_display}/{budget} "
          f"| cache_create: {cache_creation} | cache_read: {cache_read}")


def log_usage_openrouter(step: str, response, budget: int):
    """Log token usage for an OpenRouter API call."""
    u = response.usage
    prompt_tok = u.prompt_tokens if u else 0
    completion_tok = u.completion_tokens if u else 0
    total_tok = u.total_tokens if u else 0

    print(f"\n  [{step}] (OpenRouter) tokens — prompt: {prompt_tok} "
          f"| completion: {completion_tok} | total: {total_tok} "
          f"| thinking_budget: {budget}")

# ---------------------------------------------------------------------------
# Response parsing helpers
# ---------------------------------------------------------------------------

def extract_text_openrouter(response) -> str:
    """Extract text content from an OpenRouter/OpenAI chat completion response."""
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""
    msg = choices[0].message
    if msg is None:
        return ""
    if msg.content:
        return msg.content
    return ""


def strip_openrouter_json(raw: str) -> str:
    """Strip code fences from OpenRouter JSON mode responses."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw[raw.index("\n") + 1:] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:raw.rfind("```")].strip()
    return raw


def parse_json_response(raw: str, step_name: str = "") -> dict | list:
    """Parse a JSON response from OpenRouter, stripping fences."""
    stripped = strip_openrouter_json(raw)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as e:
        label = step_name or "JSON"
        print(f"paperlint [{label}] JSONDecodeError: {e}", file=sys.stderr)
        print(f"paperlint [{label}] raw length: {len(stripped)} chars", file=sys.stderr)
        preview = stripped[:800] if stripped else ""
        if len(stripped) > 800:
            preview = preview + "...(truncated)"
        print(f"paperlint [{label}] raw (first 800 chars): {repr(preview)}", file=sys.stderr)
        raise


def verify_quote_in_source(quoted_text: str, source: str) -> Citation | None:
    """Search for quoted text in the source document and return a Citation if found."""
    if not quoted_text:
        return None
    idx = source.find(quoted_text)
    if idx == -1:
        norm_q = " ".join(quoted_text.split())
        norm_s = " ".join(source.split())
        idx_norm = norm_s.find(norm_q)
        if idx_norm == -1:
            return None
        idx = source.find(quoted_text.split()[0])
        if idx == -1:
            return None
    return Citation(
        cited_text=quoted_text,
        document_index=0,
        document_title="paper",
        start_char_index=idx,
        end_char_index=idx + len(quoted_text),
    )


def extract_text_and_citations(
    response,
) -> tuple[str, list[dict], list[tuple[int, int, list[dict]]]]:
    """Reassemble full text from response content blocks and collect citations.

    Returns (full_text, all_citations, block_spans) where block_spans
    maps each text block to its character range and attached citations.
    """
    full_text = ""
    all_citations: list[dict] = []
    block_spans: list[tuple[int, int, list[dict]]] = []
    offset = 0

    for block in response.content:
        if block.type == "thinking":
            continue
        if block.type == "text":
            block_text = block.text
            block_start = offset
            block_cites: list[dict] = []
            if hasattr(block, "citations") and block.citations:
                for cite in block.citations:
                    cite_dict = {
                        "cited_text": cite.cited_text,
                        "document_index": cite.document_index,
                        "document_title": cite.document_title,
                        "start_char_index": getattr(cite, "start_char_index", None),
                        "end_char_index": getattr(cite, "end_char_index", None),
                        "text_offset_in_response": block_start,
                        "response_text": block_text,
                    }
                    all_citations.append(cite_dict)
                    block_cites.append(cite_dict)
            full_text += block_text
            offset += len(block_text)
            block_spans.append((block_start, offset, block_cites))

    return full_text, all_citations, block_spans


_FINDING_HEADING_RE = re.compile(r'^####\s+Finding\s+(\d+)\s*:', re.MULTILINE)


def map_citations_to_findings(
    discovery_text: str,
    findings: list[Finding],
    block_spans: list[tuple[int, int, list[dict]]],
) -> None:
    """Attach API citations to findings by section position in Discovery output.

    Mutates findings in place. Uses an anchored heading regex validated
    against 78 production Discovery outputs (581/581 headings, 0 false
    positives). Degrades gracefully at four levels.
    """
    total_block_citations = sum(len(cites) for _, _, cites in block_spans)
    if total_block_citations == 0:
        print("  INFO: API returned 0 citations for this paper — nothing to map")
        return

    matches = list(_FINDING_HEADING_RE.finditer(discovery_text))

    if not matches:
        print("  WARNING: No #### Finding N: sections found — skipping citation mapping")
        return

    sections: dict[int, tuple[int, int]] = {}
    for i, m in enumerate(matches):
        finding_num = int(m.group(1))
        section_start = m.start()
        section_end = matches[i + 1].start() if i + 1 < len(matches) else len(discovery_text)
        sections[finding_num] = (section_start, section_end)

    if len(sections) != len(findings):
        print(f"  WARNING: Section count ({len(sections)}) != finding count ({len(findings)})"
              " — mapping what we can")

    first_section_start = matches[0].start()
    preamble_citations = 0
    for block_start, _block_end, block_cites in block_spans:
        if block_start < first_section_start and block_cites:
            preamble_citations += len(block_cites)
    if preamble_citations:
        print(f"  INFO: {preamble_citations} citation(s) in preamble — skipped")

    mapped_count = 0
    for finding in findings:
        section_range = sections.get(finding.number)
        if section_range is None:
            continue
        sec_start, sec_end = section_range
        for block_start, _block_end, block_cites in block_spans:
            if not block_cites:
                continue
            if sec_start <= block_start < sec_end:
                for cite in block_cites:
                    finding.citations.append(Citation(
                        cited_text=cite["cited_text"],
                        document_index=cite.get("document_index", 0),
                        document_title=cite.get("document_title", "paper"),
                        start_char_index=cite.get("start_char_index", 0),
                        end_char_index=cite.get("end_char_index", 0),
                    ))
                    mapped_count += 1

    print(f"  Citations mapped: {mapped_count}/{total_block_citations}"
          f" (preamble: {preamble_citations}, sections: {len(sections)})")


def extract_findings_via_model(or_client: openai.OpenAI,
                               discovery_text: str) -> list[Finding]:
    """Extract findings from Discovery output using a model with JSON mode."""
    print("\n--- Extractor: Converting Discovery output to structured JSON ---")

    extractor_prompt = (
        "Read this Discovery output and extract every finding into a JSON object.\n\n"
        "Return ONLY a JSON object with this structure:\n"
        '{"findings": [\n'
        '  {\n'
        '    "number": 1,\n'
        '    "title": "short title of the finding",\n'
        '    "category": "rubric code e.g. 1.2",\n'
        '    "location": "section or location in paper",\n'
        '    "quoted_text": "exact quoted text from paper",\n'
        '    "defect": "what is wrong",\n'
        '    "correction": "suggested fix",\n'
        '    "axiom": "rubric axiom this violates"\n'
        '  }\n'
        ']}\n\n'
        "Extract ALL findings. Preserve the exact quoted_text — do not paraphrase.\n"
        "Return ONLY the JSON. No markdown, no explanation, no code fences."
    )

    parsed = None
    for attempt in range(2):
        response = openrouter_call_with_retry(
            or_client, "Extractor",
            model=OPENROUTER_SONNET,
            max_tokens=8_192,
            response_format={"type": "json_object"},
            messages=[
                {"role": "user", "content": f"{extractor_prompt}\n\n---\n\n{discovery_text}"},
            ],
            extra_body={},
        )

        raw = response.choices[0].message.content.strip()
        try:
            parsed = parse_json_response(raw, "Extractor")
            break
        except json.JSONDecodeError:
            if attempt == 0:
                print("  Retrying Extractor (attempt 2)...")
            else:
                raise

    raw_findings = parsed.get("findings", [])

    findings: list[Finding] = []
    for rf in raw_findings:
        findings.append(Finding(
            number=rf.get("number", 0),
            title=rf.get("title", ""),
            category=rf.get("category", ""),
            location=rf.get("location", ""),
            quoted_text=rf.get("quoted_text", ""),
            defect=rf.get("defect", ""),
            correction=rf.get("correction", ""),
            axiom=rf.get("axiom", ""),
        ))

    return findings


def format_findings_for_gate(findings: list[Finding]) -> str:
    """Format Discovery findings as text for the Gate's user message."""
    lines = ["# Candidate Findings for Verification\n"]
    lines.append("Review each finding against the paper. For each, return "
                 "PASS, REJECT, or REFER with a one-sentence reason.\n")
    for f in findings:
        lines.append(f"## Finding #{f.number}: {f.title}")
        lines.append(f"- **Category:** {f.category}")
        lines.append(f"- **Location:** {f.location}")
        lines.append(f'- **Quoted text:** "{f.quoted_text}"')
        if f.citations:
            for c in f.citations:
                lines.append(f"  - Citation: chars {c.start_char_index}-{c.end_char_index} "
                             f"in document {c.document_index}")
        lines.append(f"- **Defect:** {f.defect}")
        lines.append(f"- **Correction:** {f.correction}")
        lines.append(f"- **Axiom:** {f.axiom}")
        lines.append("")
    return "\n".join(lines)


def format_findings_for_eval(meta: PaperMeta, passed: list[GatedFinding]) -> str:
    """Format PASSed findings + metadata as the Evaluation Writer's user message."""
    lines = [
        "# Paper Metadata\n",
        f"- **Paper:** {meta.paper}",
        f"- **Title:** {meta.title}",
        f"- **Authors:** {', '.join(meta.authors)}",
        f"- **Target group:** {meta.target_group}",
        "",
        f"# Gated Findings ({len(passed)} items)\n",
    ]
    ref_num = 1
    ref_table: list[str] = []
    for g in passed:
        f = g.finding
        lines.append(f"## Finding #{f.number}: {f.title}")
        lines.append(f"- **Category:** {f.category}")
        lines.append(f"- **Location:** {f.location}")
        lines.append(f"- **Defect:** {f.defect}")
        lines.append(f"- **Correction:** {f.correction}")
        if f.citations:
            paper_cites = [c for c in f.citations if c.document_index == 0]
            if paper_cites:
                c = paper_cites[0]
                lines.append(f"- **Citation reference:** [{ref_num}]")
                ref_table.append(
                    f"[{ref_num}] {meta.paper}, chars {c.start_char_index}-"
                    f'{c.end_char_index}: "{c.cited_text[:120]}"'
                )
                ref_num += 1
        lines.append("")

    lines.append("# Citation References\n")
    lines.extend(ref_table)
    lines.append("")
    lines.append("# Rendering Instructions\n")
    lines.append("Produce the evaluation in the standard format. "
                 "Include inline reference numbers [1], [2], etc. at the end of "
                 "each finding line. Add a References section at the bottom mapping "
                 "each number to the cited text, document, and character positions. "
                 "The references table renders pre-verified citation data — do not "
                 "re-derive provenance.")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def step_metadata(paper_path: Path, anth_client: anthropic.Anthropic | None,
                   or_client: openai.OpenAI | None) -> tuple[str, PaperMeta]:
    """Step 0: Read paper and extract metadata via Sonnet."""
    print("\n--- Step 0: Reading paper and extracting metadata ---")

    is_pdf = paper_path.suffix.lower() == ".pdf"

    if is_pdf:
        _ = paper_path.read_bytes()
        paper_html = ""
    else:
        paper_html = paper_path.read_text(encoding="utf-8")

    paper_number = paper_path.stem.upper()

    try:
        clean_text = extract_text(str(paper_path))
    except Exception as e:
        print(f"  Text extraction failed: {e}")
        clean_text = paper_html[:15000] if paper_html else f"[Document: {paper_number}]"

    meta_prompt = (
        "Read this WG21 paper and return ONLY a JSON object with these fields:\n\n"
        '{\n'
        '  "title": "the paper title",\n'
        '  "authors": ["author1", "author2"],\n'
        '  "audience": "target working group(s) e.g. LEWG, CWG",\n'
        '  "paper_type": "wording or proposal or directional",\n'
        '  "abstract": "A 2-3 sentence summary of what this paper proposes or addresses. '
        'Write clearly and precisely. Describe the paper\'s contribution, not its structure."\n'
        '}\n\n'
        "Return ONLY the JSON. No markdown, no explanation, no code fences."
    )

    title = "Unknown"
    authors: list[str] = []
    audience = "Unknown"
    paper_type = "wording"
    abstract = ""

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = or_client.chat.completions.create(
                model=OPENROUTER_SONNET,
                max_tokens=512,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "user", "content": f"{meta_prompt}\n\n{clean_text}"},
                ],
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("API returned empty content")
            raw = content.strip()

            parsed = json.loads(strip_openrouter_json(raw))
            title = parsed.get("title", "Unknown")
            authors = parsed.get("authors", [])
            if isinstance(authors, str):
                authors = [a.strip() for a in authors.split(",")]
            audience = parsed.get("audience", "Unknown")
            paper_type = parsed.get("paper_type", "wording")
            abstract = parsed.get("abstract", "")
            if title != "Unknown" and audience != "Unknown":
                print("  Sonnet metadata: OK")
                break
            print(f"  Sonnet metadata: incomplete (attempt {attempt}/{max_retries})")
            if attempt < max_retries:
                time.sleep(2)
        except (json.JSONDecodeError, Exception) as e:
            print(f"  Sonnet metadata: FAILED attempt {attempt}/{max_retries} ({e})")
            if attempt < max_retries:
                time.sleep(2)

    meta = PaperMeta(
        paper=paper_number,
        title=title,
        authors=authors,
        target_group=audience,
        paper_type=paper_type,
        abstract=abstract,
        source_file=str(paper_path),
        run_timestamp=datetime.now(timezone.utc).isoformat(),
        model=ANTHROPIC_MODEL,
    )

    print(f"  Paper: {meta.paper}")
    print(f"  Title: {meta.title}")
    print(f"  Authors: {', '.join(meta.authors)}")
    print(f"  Target group: {meta.target_group}")
    print(f"  Paper type: {meta.paper_type}")
    print(f"  Abstract: {meta.abstract[:100]}...")
    return clean_text, meta


def step_discovery_anthropic(
    client: anthropic.Anthropic, clean_text: str, meta: PaperMeta,
) -> tuple[str, list[dict], list[str], list[tuple[int, int, list[dict]]]]:
    """Step 1 (Anthropic path): Discovery with Citations API."""
    print("\n--- Step 1: Calling Discovery Agent (Anthropic + Citations) ---")

    rubric_text = RUBRIC_PATH.read_text(encoding="utf-8")
    skill_text = (PROMPTS_DIR / "1-discovery.md").read_text(encoding="utf-8")
    system_prompt = f"{skill_text}\n\n---\n\n# Evaluation Rubric\n\n{rubric_text}"

    doc_source = {
        "type": "text",
        "media_type": "text/plain",
        "data": clean_text,
    }

    response = anthropic_call_with_retry(
        client, "Discovery",
        model=ANTHROPIC_MODEL,
        max_tokens=MAX_TOKENS["discovery"],
        timeout=600.0,
        thinking={
            "type": "enabled",
            "budget_tokens": THINKING_BUDGET["discovery"],
        },
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": doc_source,
                    "title": f"{meta.paper} — {meta.title}",
                    "context": json.dumps({
                        "target_group": meta.target_group,
                        "authors": ", ".join(meta.authors),
                    }),
                    "citations": {"enabled": True},
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "text",
                    "text": "Analyze this paper for objective defects per the rubric.",
                },
            ],
        }],
    )

    log_usage_anthropic("Discovery", response, THINKING_BUDGET["discovery"])

    debug_lines = []
    for i, block in enumerate(response.content):
        debug_lines.append(f"--- Block {i}: type={block.type} ---")
        if block.type == "thinking":
            debug_lines.append(f"  thinking: {block.thinking[:200]}...")
        elif block.type == "text":
            debug_lines.append(f"  text: {block.text[:200]}...")
            cites = getattr(block, "citations", None)
            debug_lines.append(f"  citations attr: {type(cites)} len={len(cites) if cites else 0}")
            if cites:
                for j, c in enumerate(cites[:3]):
                    debug_lines.append(f"    cite[{j}]: type={c.type} doc={c.document_index} "
                                       f"text={c.cited_text[:60]}...")

    full_text, citations, block_spans = extract_text_and_citations(response)

    _print_discovery_summary([], citations)
    return full_text, citations, debug_lines, block_spans


def step_discovery_openrouter(
    or_client: openai.OpenAI, clean_text: str, meta: PaperMeta,
) -> tuple[str, list[dict], list[str], list[tuple[int, int, list[dict]]]]:
    """Step 1 (OpenRouter path): Discovery without Citations API."""
    print("\n--- Step 1: Calling Discovery Agent (OpenRouter) ---")

    rubric_text = RUBRIC_PATH.read_text(encoding="utf-8")
    skill_text = (PROMPTS_DIR / "1-discovery.md").read_text(encoding="utf-8")
    system_prompt = f"{skill_text}\n\n---\n\n# Evaluation Rubric\n\n{rubric_text}"

    user_content = (
        f"<paper title=\"{meta.paper} — {meta.title}\" "
        f"target_group=\"{meta.target_group}\" "
        f"authors=\"{', '.join(meta.authors)}\">\n"
        f"{clean_text}\n"
        f"</paper>\n\n"
        f"Analyze this paper for objective defects per the rubric."
    )

    response = openrouter_call_with_retry(
        or_client, "Discovery",
        model=OPENROUTER_MODEL,
        max_tokens=MAX_TOKENS["discovery"],
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

    log_usage_openrouter("Discovery", response, THINKING_BUDGET["discovery"])

    full_text = extract_text_openrouter(response)

    debug_lines = [
        "--- OpenRouter path (no API citations) ---",
        f"  Full text length: {len(full_text)}",
    ]

    _print_discovery_summary([], [])
    return full_text, [], debug_lines, []


def _print_discovery_summary(findings: list[Finding], api_citations: list):
    src = "api" if api_citations else "local"
    print(f"  Findings extracted: {len(findings)}")
    verified = sum(1 for f in findings if f.citations)
    print(f"  Findings with verified citations: {verified}/{len(findings)}")
    for f in findings:
        print(f"    #{f.number}: {f.title} [{f.category}] — "
              f"{len(f.citations)} citations ({src})")


def step_gate(or_client: openai.OpenAI, paper_text: str,
              meta: PaperMeta, findings: list[Finding]) -> list[GatedFinding]:
    """Step 2: Call Verification Gate via OpenRouter."""
    print("\n--- Step 2: Calling Verification Gate (OpenRouter) ---")

    if not findings:
        print("  No findings to gate.")
        return []

    system_prompt = (PROMPTS_DIR / "2-verification-gate.md").read_text(encoding="utf-8")
    findings_text = format_findings_for_gate(findings)

    user_content = (
        f"<paper title=\"{meta.paper} — {meta.title}\">\n"
        f"{paper_text}\n"
        f"</paper>\n\n"
        f"{findings_text}"
    )

    json_instruction = (
        "\n\n## Output Format\n\n"
        "Return ONLY a JSON object with this structure:\n"
        '{"verdicts": [\n'
        '  {"finding_number": 1, "verdict": "PASS", "reason": "why this finding holds up"},\n'
        '  {"finding_number": 2, "verdict": "REJECT", "reason": "why this finding does not hold up"}\n'
        ']}\n\n'
        "verdict must be exactly one of: PASS, REJECT, REFER.\n"
        "Return ONLY the JSON. No markdown, no explanation."
    )

    response = openrouter_call_with_retry(
        or_client, "Gate",
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

    log_usage_openrouter("Gate", response, THINKING_BUDGET["gate"])

    raw = extract_text_openrouter(response)
    if not raw.strip():
        n_choices = len(getattr(response, "choices", None) or [])
        msg = (
            f"paperlint [Gate] Empty model response for paper={meta.paper!r} "
            f"(choices={n_choices}). Check provider logs / moderation / max_tokens."
        )
        print(msg, file=sys.stderr)
        raise RuntimeError(msg)

    try:
        parsed = parse_json_response(raw, f"Gate paper={meta.paper}")
    except json.JSONDecodeError:
        print(
            f"paperlint [Gate] context: paper={meta.paper!r} "
            f"user_message_chars={len(user_content)} findings={len(findings)}",
            file=sys.stderr,
        )
        raise
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


def step_eval_writer(or_client: openai.OpenAI, meta: PaperMeta,
                     gated: list[GatedFinding]) -> dict:
    """Step 3: Call Evaluation Writer via OpenRouter (JSON mode)."""
    print("\n--- Step 3: Calling Evaluation Writer (OpenRouter, JSON mode) ---")

    passed = [g for g in gated if g.verdict == "PASS"]
    system_prompt = (PROMPTS_DIR / "3-evaluation-writer.md").read_text(encoding="utf-8")

    json_instruction = (
        "\n\n## Output Format\n\n"
        "Return ONLY a JSON object with this structure:\n"
        '{\n'
        '  "summary": "2-3 sentence evaluation summary — what the paper proposes and what was found. Plain text, no markdown.",\n'
        '  "findings": [\n'
        '    {\n'
        '      "location": "§X.Y or section name",\n'
        '      "description": "one-line plain text description of the defect. No markdown, no bold, no asterisks."\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        "Do NOT include references — those are assembled separately from citation data.\n"
        "Do NOT use markdown formatting in any string value — plain text only.\n"
        "Return ONLY the JSON. No explanation."
    )

    user_message = format_findings_for_eval(meta, passed)

    if not passed:
        print("  No passed findings — producing clean eval.")
        return {
            "summary": f"No objective problems found in {meta.paper} — {meta.title}.",
            "findings": [],
            "references": [],
        }

    response = openrouter_call_with_retry(
        or_client, "Eval Writer",
        model=OPENROUTER_MODEL,
        max_tokens=MAX_TOKENS["report_writer"],
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt + json_instruction},
            {"role": "user", "content": user_message},
        ],
        extra_body={
            "thinking": {
                "type": "enabled",
                "budget_tokens": THINKING_BUDGET["report_writer"],
            },
        },
    )

    log_usage_openrouter("Eval Writer", response, THINKING_BUDGET["report_writer"])

    raw = extract_text_openrouter(response)
    if not raw:
        print("  WARNING: Eval Writer returned empty response. Falling back.")
        return {
            "summary": f"Evaluation of {meta.paper} — {meta.title}.",
            "findings": [],
        }
    try:
        return json.loads(strip_openrouter_json(raw))
    except json.JSONDecodeError as e:
        print(f"  WARNING: Eval Writer JSON parse failed: {e}")
        print(f"  Raw response (first 500 chars): {raw[:500]}")
        return {
            "summary": f"Evaluation of {meta.paper} — {meta.title}.",
            "findings": [],
        }

# ---------------------------------------------------------------------------
# Paper fetching
# ---------------------------------------------------------------------------

OPEN_STD_BASE = "https://www.open-std.org/jtc1/sc22/wg21/docs/papers"


def _looks_like_open_std_doc_id(paper_ref: str) -> bool:
    """True if paper_ref is a bare P- or N-prefixed open-std document id."""
    u = paper_ref.strip().upper()
    if not u or "/" in u or "\\" in u:
        return False
    if len(u) < 2 or u[0] not in ("P", "N"):
        return False
    return u[1].isdigit()


def fetch_paper(paper_id: str, cache_dir: Path | None = None) -> Path:
    """Fetch a WG21 document by ID (e.g., P3642R4). Returns local file path.

    Checks local cache first. If not found, downloads from open-std.org.
    Tries HTML first, then PDF. Caches locally for future runs.
    """
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
                continue

    raise FileNotFoundError(f"Could not find {paper_id} on open-std.org (tried HTML and PDF for 2024-2026)")


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------

def run_paper_eval(
    paper_ref: str,
    *,
    output_dir: Path,
    all_openrouter: bool = False,
) -> dict:
    """Evaluate one paper. Write evaluation.json to output_dir.

    Returns the evaluation dict for use by batch callers.
    """
    paper_path = Path(paper_ref)
    if paper_path.exists():
        pass
    elif _looks_like_open_std_doc_id(paper_ref):
        print(f"Fetching {paper_ref}...")
        paper_path = fetch_paper(paper_ref.upper())
    else:
        print(f"Error: {paper_ref} not found", file=sys.stderr)
        raise FileNotFoundError(paper_ref)

    ensure_api_keys(all_openrouter=all_openrouter)

    or_client = openai.OpenAI(
        base_url=resolve_openrouter_base_url(),
        api_key=os.environ["OPENROUTER_API_KEY"],
    )

    anth_client = None
    if not all_openrouter:
        anth_client = anthropic.Anthropic()

    paper_id = paper_path.stem
    paper_output_dir = output_dir / paper_id
    paper_output_dir.mkdir(parents=True, exist_ok=True)

    # Step 0: Metadata
    clean_text, meta = step_metadata(paper_path, anth_client, or_client)
    if meta.title == "Unknown":
        print(f"\n{'=' * 60}")
        print(f"SKIPPED: {meta.paper} — metadata extraction failed after retries.")
        print(f"{'=' * 60}")
        return {}

    meta_path = paper_output_dir / "meta.json"
    meta_path.write_text(json.dumps(asdict(meta), indent=2), encoding="utf-8")
    print(f"  Written: {meta_path}")

    # Step 1: Discovery
    if anth_client:
        discovery_text, citations, debug_lines, block_spans = step_discovery_anthropic(
            anth_client, clean_text, meta)
    else:
        discovery_text, citations, debug_lines, block_spans = step_discovery_openrouter(
            or_client, clean_text, meta)
    disc_path = paper_output_dir / "1-discovery-raw.md"
    disc_path.write_text(discovery_text, encoding="utf-8")
    print(f"  Written: {disc_path}")

    debug_path = paper_output_dir / "1-discovery-debug.txt"
    debug_path.write_text("\n".join(debug_lines), encoding="utf-8")

    # Step 1b: Extractor
    findings = extract_findings_via_model(or_client, discovery_text)

    # Step 1c: Citation mapping
    if block_spans:
        map_citations_to_findings(discovery_text, findings, block_spans)

    findings_path = paper_output_dir / "2-findings.json"
    findings_path.write_text(json.dumps([asdict(f) for f in findings], indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Findings extracted: {len(findings)}")
    print(f"  Written: {findings_path}")

    # Step 2: Gate
    gated = step_gate(or_client, clean_text, meta, findings)
    gate_path = paper_output_dir / "3-gate.json"
    gate_path.write_text(json.dumps([{"finding_number": g.finding.number, "verdict": g.verdict, "reason": g.reason} for g in gated], indent=2), encoding="utf-8")
    print(f"  Written: {gate_path}")

    # Step 3: Evaluation Writer
    eval_result = step_eval_writer(or_client, meta, gated)
    eval_path = paper_output_dir / "4-eval.json"
    eval_path.write_text(json.dumps(eval_result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Written: {eval_path}")

    # Step 4: Assembly
    passed = [g for g in gated if g.verdict == "PASS"]
    rejected = [g for g in gated if g.verdict == "REJECT"]

    references = []
    eval_findings = eval_result.get("findings", [])
    for i, gf in enumerate(passed):
        ref_num = i + 1
        if i < len(eval_findings):
            eval_findings[i]["reference_number"] = ref_num
        for cite in gf.finding.citations:
            references.append({
                "number": ref_num,
                "cited_text": cite.cited_text,
                "start_char": cite.start_char_index,
                "end_char": cite.end_char_index,
            })
        if not gf.finding.citations and gf.finding.quoted_text:
            if block_spans:
                print(f"  WARNING: Finding {ref_num} has no API citations (mapping failure)")
            references.append({
                "number": ref_num,
                "cited_text": gf.finding.quoted_text,
                "start_char": None,
                "end_char": None,
            })

    # Citation accounting
    api_total = len(citations)
    cites_on_pass = sum(len(gf.finding.citations) for gf in passed)
    cites_on_reject = sum(len(gf.finding.citations) for gf in rejected)
    cites_in_output = sum(1 for r in references if r["start_char"] is not None)
    cites_mapped = sum(len(f.citations) for f in findings)
    mapping_loss = api_total - cites_mapped
    preamble_count = api_total - cites_mapped if api_total > cites_mapped else 0
    print(f"\n  Citations: API returned={api_total}, mapped={cites_mapped},"
          f" on PASS={cites_on_pass}, on REJECT={cites_on_reject},"
          f" in output={cites_in_output}, mapping loss={mapping_loss - preamble_count}"
          f" (preamble={preamble_count})")

    eval_json = {
        "schema_version": SCHEMA_VERSION,
        "paperlint_sha": _git_sha(),
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
        "summary": eval_result.get("summary", ""),
        "findings": eval_findings,
        "references": references,
    }

    json_path = paper_output_dir / "evaluation.json"
    json_path.write_text(json.dumps(eval_json, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Written: {json_path}")

    flat_path = output_dir / f"{meta.paper}.json"
    flat_path.write_text(json.dumps(eval_json, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Written: {flat_path}")

    print(f"\n{'=' * 60}")
    print(f"Pipeline complete. Deliverable: {flat_path}")
    print(f"{'=' * 60}")

    return eval_json
