#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Pipeline steps: metadata, discovery, quote verification, gate, summary."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import openai

from paperlint.extract import extract_text
from paperlint.llm import (
    OPENROUTER_MODEL,
    OPENROUTER_SONNET,
    THINKING_BUDGET,
    MAX_TOKENS,
    call_with_retry,
    extract_response_text,
    log_usage,
    parse_json,
    strip_fences,
)
from paperlint.models import Evidence, Finding, GatedFinding, PaperMeta

_PKG_ROOT = Path(__file__).resolve().parent
PROMPTS_DIR = _PKG_ROOT / "prompts"
RUBRIC_PATH = _PKG_ROOT / "rubric.md"


def normalized_char_offset_map(source_text: str) -> tuple[str, list[int]]:
    """Build ``' '.join(source_text.split())`` and map each normalized index to ``source_text``."""
    parts = source_text.split()
    if not parts:
        return "", []
    norm_to_orig: list[int] = []
    pos = 0
    for pi, part in enumerate(parts):
        idx = source_text.find(part, pos)
        if idx < 0:
            raise RuntimeError("internal error: split() token not found in source_text")
        if pi > 0:
            ws_start = idx - 1
            while ws_start >= pos and source_text[ws_start] in " \t\n\r":
                ws_start -= 1
            ws_start += 1
            norm_to_orig.append(ws_start)
        for k in range(len(part)):
            norm_to_orig.append(idx + k)
        pos = idx + len(part)
    source_norm = " ".join(parts)
    if len(norm_to_orig) != len(source_norm):
        raise RuntimeError(
            f"internal error: norm map length {len(norm_to_orig)} vs norm len {len(source_norm)}"
        )
    return source_norm, norm_to_orig


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


def step_metadata(paper_path: Path, mailing_meta: dict) -> tuple[str, PaperMeta]:
    """Step 0: Build PaperMeta from the authoritative mailing index and extract paper text.

    The open-std.org mailing index is authoritative for title, authors, audience, and
    paper_type. No LLM call is made for metadata; the index is ground truth.
    """
    print("\n--- Step 0: Metadata (from mailing index) ---")

    paper_number = paper_path.stem.upper()

    try:
        clean_text = extract_text(str(paper_path), mailing_meta=mailing_meta)
    except Exception as e:
        print(f"  Text extraction failed: {e}")
        if paper_path.suffix.lower() != ".pdf":
            clean_text = paper_path.read_text(encoding="utf-8")[:15000]
        else:
            clean_text = f"[Document: {paper_number}]"

    authors = mailing_meta.get("authors", []) or []
    if isinstance(authors, str):
        authors = [a.strip() for a in authors.split(",") if a.strip()]

    meta = PaperMeta(
        paper=paper_number,
        title=mailing_meta.get("title", "") or "",
        authors=authors,
        target_group=mailing_meta.get("subgroup", "") or "",
        paper_type=mailing_meta.get("paper_type", "proposal") or "proposal",
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
        f"Analyze this paper for objective defects per the rubric.\n\n"
        f"IMPORTANT: Return ONLY a valid JSON object. No markdown. No explanation."
    )

    parsed = None
    for attempt in range(3):
        response = call_with_retry(
            client,
            "Discovery",
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

        log_usage("Discovery", response, THINKING_BUDGET["discovery"])

        raw = extract_response_text(response)
        try:
            parsed = parse_json(raw, "Discovery")
            break
        except json.JSONDecodeError:
            if attempt < 2:
                print(
                    f"  Retrying Discovery (JSON parse failed, attempt {attempt + 2})..."
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
        findings.append(
            Finding(
                number=rf.get("number", 0),
                title=rf.get("title", ""),
                category=rf.get("category", ""),
                defect=rf.get("defect", ""),
                correction=rf.get("correction", ""),
                axiom=rf.get("axiom", ""),
                evidence=evidence,
            )
        )

    print(f"  Findings: {len(findings)}")
    for f in findings:
        print(f"    #{f.number}: {f.title[:60]} ({len(f.evidence)} evidence)")

    return findings


def step_verify_quotes(findings: list[Finding], source_text: str) -> list[Finding]:
    """Step 1b: Programmatic quote verification — reject findings with unverifiable evidence."""
    print("\n--- Step 1b: Quote Verification ---")

    source_norm, norm_to_orig = normalized_char_offset_map(source_text)
    verified_findings: list[Finding] = []

    for f in findings:
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
                if norm_idx >= 0 and norm_quote:
                    ev.verified = True
                    ev.extracted_char_start = norm_to_orig[norm_idx]
                    end_norm = norm_idx + len(norm_quote)
                    ev.extracted_char_end = norm_to_orig[end_norm - 1] + 1
                    status = "NORM"
                else:
                    ev.verified = False
                    status = "MISS"
            print(f"    #{f.number} [{status}] \"{ev.quote[:60]}\"")

        if f.evidence and all(ev.verified for ev in f.evidence):
            verified_findings.append(f)
        else:
            unverified = sum(1 for ev in f.evidence if not ev.verified)
            print(f"    #{f.number} DROPPED — {unverified} unverifiable quote(s)")

    dropped = len(findings) - len(verified_findings)
    if dropped:
        print(f"  Dropped {dropped} finding(s) with no verifiable evidence")
    print(f"  Verified: {len(verified_findings)}/{len(findings)}")

    return verified_findings


def step_gate(
    client: openai.OpenAI,
    paper_text: str,
    meta: PaperMeta,
    findings: list[Finding],
) -> list[GatedFinding]:
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
        '  {"finding_number": 1, "verdict": "PASS", "reason": "...", "judgment": false}\n'
        ']}\n'
        "verdict must be PASS, REJECT, or REFER.\n"
        "judgment: true if reaching this verdict required judgment beyond mechanical verification, false if purely mechanical.\n"
        "Return ONLY the JSON."
    )

    parsed = None
    for attempt in range(3):
        response = call_with_retry(
            client,
            "Gate",
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

        log_usage("Gate", response, THINKING_BUDGET["gate"])

        raw = extract_response_text(response)
        if not raw.strip():
            if attempt == 0:
                print("  Retrying Gate (empty response, attempt 2)...")
                continue
            raise RuntimeError(f"paperlint [Gate] Empty response for {meta.paper}")

        try:
            parsed = parse_json(raw, f"Gate paper={meta.paper}")
            break
        except json.JSONDecodeError:
            if attempt < 2:
                print(f"  Retrying Gate (JSON parse failed, attempt {attempt + 2})...")
            else:
                raise

    verdicts = parsed.get("verdicts", [])

    gated: list[GatedFinding] = []
    verdict_map = {v["finding_number"]: v for v in verdicts}
    judgment_rejections = 0
    for f in findings:
        v = verdict_map.get(f.number, {"verdict": "REFER", "reason": "No verdict returned"})
        verdict = v.get("verdict", "REFER").upper()
        reason = v.get("reason", "")
        used_judgment = v.get("judgment", False)
        if verdict == "PASS" and used_judgment:
            verdict = "REJECT"
            reason = f"Auto-rejected: gate reported judgment was required. Original: {reason}"
            judgment_rejections += 1
        gated.append(
            GatedFinding(
                finding=f,
                verdict=verdict,
                reason=reason,
            )
        )

    passed = [g for g in gated if g.verdict == "PASS"]
    rejected = [g for g in gated if g.verdict == "REJECT"]
    referred = [g for g in gated if g.verdict == "REFER"]
    print(f"  PASS: {len(passed)} | REJECT: {len(rejected)} | REFER: {len(referred)}")
    if judgment_rejections:
        print(f"  ({judgment_rejections} auto-rejected: PASS with judgment)")
    for g in gated:
        print(f"    #{g.finding.number}: {g.verdict} — {g.reason[:80]}")

    return gated


def step_summary_writer(client: openai.OpenAI, meta: PaperMeta, n_findings: int) -> str:
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
        '{"summary": "1-2 sentence characterization of what the evaluation found. Plain text."}\n\n'
        "Write ONLY the summary. Findings are assembled separately.\n"
        "Return ONLY the JSON."
    )

    user_content = (
        f"Paper: {meta.paper} — {meta.title}\n"
        f"Authors: {', '.join(meta.authors)}\n"
        f"Audience: {meta.target_group}\n"
        f"Type: {meta.paper_type}\n\n"
        f"Number of findings that passed verification: {n_findings}\n\n"
        f"Summarize what the evaluation found. Characterize the findings "
        f"at the level of categories and sections — do not list each one. "
        f"Do not describe what the paper proposes; the reader already knows."
    )

    response = call_with_retry(
        client,
        "Summary",
        model=OPENROUTER_SONNET,
        max_tokens=512,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt + json_instruction},
            {"role": "user", "content": user_content},
        ],
    )

    raw = extract_response_text(response)
    try:
        parsed = json.loads(strip_fences(raw))
        summary = parsed.get("summary", f"Evaluation of {meta.paper}.")
    except json.JSONDecodeError:
        summary = f"Evaluation of {meta.paper} — {meta.title}."

    preview = summary[:100]
    suffix = "..." if len(summary) > 100 else ""
    print(f"  Summary: {preview}{suffix}")
    return summary
