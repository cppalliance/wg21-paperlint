#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Pipeline steps: discovery, quote verification, gate, summary.

Metadata extraction (formerly ``step_metadata``) moved to
``tomd.api.convert_paper`` + ``paperlint.orchestrator.convert_one_paper``
in the 0.2 restructure; this module no longer imports from tomd.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import openai

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


def _discovery_json_schema() -> str:
    return (
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


def _raw_findings_to_objects(raw_findings: list) -> list[Finding]:
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
    return findings


def _run_discovery_call(
    client: openai.OpenAI,
    *,
    system_prompt: str,
    user_content: str,
    step_label: str,
) -> list[Finding]:
    """One LLM discovery call with JSON-parse retries (same as legacy single-pass)."""
    parsed = None
    for attempt in range(3):
        response = call_with_retry(
            client,
            step_label,
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

        log_usage(step_label, response, THINKING_BUDGET["discovery"])

        raw = extract_response_text(response)
        try:
            parsed = parse_json(raw, step_label)
            break
        except json.JSONDecodeError:
            if attempt < 2:
                print(
                    f"  Retrying {step_label} (JSON parse failed, attempt {attempt + 2})..."
                )
            else:
                raise

    raw_findings = parsed.get("findings", [])
    return _raw_findings_to_objects(raw_findings)


def _dedup_finding_key(f: Finding) -> tuple[str, str, str]:
    """Stable signature for deduplicating findings across discovery passes."""
    cat = f.category.strip().lower()
    if f.evidence:
        ev0 = f.evidence[0]
        loc = ev0.location.strip().lower()
        q = ev0.quote
        qnorm = " ".join(q.split())[:120].lower()
    else:
        loc = ""
        qnorm = ""
    return (cat, loc, qnorm)


def _format_prior_findings(prior: list[Finding]) -> str:
    """User-message block listing defects already found (pass 2+ context)."""
    lines = [
        "\n\n## Previously Found Defects (do NOT repeat)\n",
        "The following defects have already been identified. Do not report them again. "
        "Find ONLY additional defects you can verify in the paper that are not already "
        "listed.\n",
    ]
    for i, f in enumerate(prior, 1):
        lines.append(f"### Prior #{i}: {f.title}")
        lines.append(f"- **Category:** {f.category}")
        if f.evidence:
            ev = f.evidence[0]
            lines.append(f"- **Location:** {ev.location}")
            excerpt = ev.quote[:200].replace("\n", " ")
            lines.append(f'- **Quote excerpt:** "{excerpt}"')
        lines.append("")
    return "\n".join(lines)


def _merge_pass(
    accumulated: list[Finding], new_findings: list[Finding]
) -> tuple[list[Finding], int]:
    """Append findings whose dedup key is not already present. Returns (accumulator, n_new)."""
    existing_keys = {_dedup_finding_key(f) for f in accumulated}
    new_added = 0
    for f in new_findings:
        k = _dedup_finding_key(f)
        if k in existing_keys:
            continue
        existing_keys.add(k)
        accumulated.append(f)
        new_added += 1
    return accumulated, new_added


def step_discovery(
    client: openai.OpenAI,
    clean_text: str,
    meta: PaperMeta,
    *,
    passes: int = 3,
) -> list[Finding]:
    """Step 1: Discovery — find defects, output structured JSON with evidence.

    When ``passes`` > 1, runs multiple LLM calls. Pass 1 is a full discovery pass;
    each later pass is shown prior accumulated findings and asked to add only
    defects not already listed. Results are merged with programmatic dedup on
    (category, first-evidence location, first-evidence quote prefix), then
    renumbered 1..N for downstream gate/verification.
    """
    if passes < 1:
        raise ValueError(
            f"step_discovery: passes must be >= 1, got {passes!r} (paper={meta.paper})"
        )

    print("\n--- Step 1: Discovery (JSON mode + thinking) ---")

    rubric_text = RUBRIC_PATH.read_text(encoding="utf-8")
    skill_text = (PROMPTS_DIR / "1-discovery.md").read_text(encoding="utf-8")
    json_schema = _discovery_json_schema()
    system_prompt = f"{skill_text}\n\n---\n\n# Evaluation Rubric\n\n{rubric_text}{json_schema}"

    base_user = (
        f"<paper title=\"{meta.paper} — {meta.title}\" "
        f"target_group=\"{meta.target_group}\" "
        f"authors=\"{', '.join(meta.authors)}\">\n"
        f"{clean_text}\n"
        f"</paper>\n\n"
        f"Analyze this paper for objective defects per the rubric.\n\n"
        f"IMPORTANT: Return ONLY a valid JSON object. No markdown. No explanation."
    )

    accumulated: list[Finding] = []
    last_pass_exc: Exception | None = None

    for pass_idx in range(passes):
        if pass_idx == 0:
            user_content = base_user
        else:
            prior_block = _format_prior_findings(accumulated)
            directive = (
                "\n\nThese defects have already been reported. Find ONLY additional "
                "defects you can verify in the paper that are not already on the list above."
            )
            user_content = base_user + prior_block + directive

        step_label = "Discovery" if passes == 1 else f"Discovery pass {pass_idx + 1}/{passes}"
        try:
            batch = _run_discovery_call(
                client,
                system_prompt=system_prompt,
                user_content=user_content,
                step_label=step_label,
            )
            raw_count = len(batch)
            accumulated, n_new = _merge_pass(accumulated, batch)
            dupes = raw_count - n_new
            if passes > 1:
                print(
                    f"  Pass {pass_idx + 1}/{passes}: {raw_count} found, "
                    f"{n_new} new, {dupes} duplicate(s) vs prior"
                )
        except Exception as e:
            last_pass_exc = e
            print(
                f"  Pass {pass_idx + 1}/{passes} failed: {type(e).__name__}: {e}",
                file=sys.stderr,
            )

    if not accumulated and last_pass_exc is not None:
        raise last_pass_exc

    for i, f in enumerate(accumulated, start=1):
        f.number = i

    print(f"  Findings: {len(accumulated)}")
    for f in accumulated:
        print(f"    #{f.number}: {f.title[:60]} ({len(f.evidence)} evidence)")

    return accumulated


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
