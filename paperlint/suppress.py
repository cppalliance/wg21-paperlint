#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Known false-positive suppression for paperlint.

Runs as a post-gate filter. Given the list of gated findings, drops any
finding matching one of the reviewer-confirmed extraction-artifact signatures
catalogued in cppa-home/plans/paperlint-fp-catalog-2026-04-15.md.

Shipping for April 19: three signature classes.

1. Intra-word spacing — PDF extraction splits a capitalized word across
   whitespace (e.g. "T ooling" for "Tooling"). Signature: defect text uses
   specific phrasings on the class AND evidence quote contains the split
   pattern.

2. TOC location suppression — findings sourced from Table of Contents are
   suppressed as a category. Every TOC finding in the review corpus has
   been a false positive because dot-leader layout confuses extraction.
   Real TOC defects are already caught by the body-section numbering
   checks discovery runs separately.

3. Bracketed identifier layout wrap — WG21 stable names inside brackets
   are hyphenless and spaceless by convention. A bracketed compound with
   internal whitespace (e.g. "[meta.reflection. member.queries]") is
   essentially always a layout-wrap extraction artifact.

Five additional classes from the catalog are deferred pending either
tighter deterministic signatures, an LLM-subagent classifier approach, or
extractor upgrades: multi-line bibliography wrap, color-coded diff
flattening, code block line-break collapse, hyphen-wrap collapse producing
non-words, and font-change rendering artifacts.

The mechanism is fail-closed: matching findings are dropped, not
downgraded. Non-PASS findings (REJECT, REFER) pass through untouched. The
suppressed findings are recorded in 2c-suppressed.json for audit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from paperlint.models import Finding, GatedFinding, PaperMeta


@dataclass
class SuppressionMatch:
    """Record of a single finding being suppressed by a signature."""
    signature_name: str
    reason: str
    matched_pattern: str
    finding_number: int
    evidence_quote_snippet: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_pdf(meta: PaperMeta) -> bool:
    return meta.source_file.lower().endswith(".pdf")


def _snippet(text: str, start: int, end: int, context: int = 40) -> str:
    s = max(0, start - context)
    e = min(len(text), end + context)
    return text[s:e]


# ---------------------------------------------------------------------------
# Signature 1: Intra-word spacing artifacts
# ---------------------------------------------------------------------------

_INTRA_WORD_DEFECT_KEYWORDS = (
    "intra-word spacing",
    "space splitting",
    "line break or space",
    "rendered with a line break",
    "line break or space splitting",
    "spurious space between",
    "line-break artifact",
    "rendering artifact",
    "rendering/line-break",
)

_INTRA_WORD_EVIDENCE_RE = re.compile(r"\b[A-Z]\s+[a-z]{2,}\b")


def _is_intra_word_spacing(
    finding: Finding, meta: PaperMeta
) -> SuppressionMatch | None:
    if not _is_pdf(meta):
        return None
    defect_lower = finding.defect.lower()
    if not any(kw in defect_lower for kw in _INTRA_WORD_DEFECT_KEYWORDS):
        return None
    for ev in finding.evidence:
        m = _INTRA_WORD_EVIDENCE_RE.search(ev.quote)
        if m:
            return SuppressionMatch(
                signature_name="intra_word_spacing",
                reason="PDF extraction split a capitalized word across whitespace",
                matched_pattern=m.group(0),
                finding_number=finding.number,
                evidence_quote_snippet=_snippet(ev.quote, m.start(), m.end()),
            )
    return None


# ---------------------------------------------------------------------------
# Signature 2: TOC location suppression
# ---------------------------------------------------------------------------

_TOC_LOCATION_RE = re.compile(r"(table of contents|\btoc\b)", re.IGNORECASE)


def _is_toc_location(
    finding: Finding, meta: PaperMeta
) -> SuppressionMatch | None:
    if not finding.evidence:
        return None
    primary_location = finding.evidence[0].location
    m = _TOC_LOCATION_RE.search(primary_location)
    if m:
        return SuppressionMatch(
            signature_name="toc_location",
            reason="finding sourced from Table of Contents, category suppressed under precision discipline",
            matched_pattern=m.group(0),
            finding_number=finding.number,
            evidence_quote_snippet=primary_location,
        )
    return None


# ---------------------------------------------------------------------------
# Signature 3: Bracketed identifier layout wrap
# ---------------------------------------------------------------------------

_BRACKETED_WRAP_EVIDENCE_RE = re.compile(r"\[[a-zA-Z0-9._]+\s+[a-zA-Z0-9._]+\]")

_BRACKETED_WRAP_DEFECT_KEYWORDS = (
    "spurious space",
    "malformed",
    "layout",
    "line break",
    "extra space",
    "stable name",
)


def _is_bracketed_identifier_layout_wrap(
    finding: Finding, meta: PaperMeta
) -> SuppressionMatch | None:
    if not _is_pdf(meta):
        return None
    defect_lower = finding.defect.lower()
    if not any(kw in defect_lower for kw in _BRACKETED_WRAP_DEFECT_KEYWORDS):
        return None
    for ev in finding.evidence:
        m = _BRACKETED_WRAP_EVIDENCE_RE.search(ev.quote)
        if m:
            return SuppressionMatch(
                signature_name="bracketed_identifier_layout_wrap",
                reason="bracketed stable name contains internal whitespace, likely PDF layout-wrap artifact",
                matched_pattern=m.group(0),
                finding_number=finding.number,
                evidence_quote_snippet=_snippet(ev.quote, m.start(), m.end()),
            )
    return None


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_SIGNATURES = (
    _is_intra_word_spacing,
    _is_toc_location,
    _is_bracketed_identifier_layout_wrap,
)


def step_suppress_known_fps(
    gated: list[GatedFinding],
    meta: PaperMeta,
) -> tuple[list[GatedFinding], list[dict]]:
    """Suppress gated findings matching known false-positive signatures.

    Only PASS findings are examined. REJECT and REFER findings pass through
    untouched — they are already not going to reviewers. For each PASS finding,
    each signature is tried in turn; the first match wins. Matching findings
    are removed from the kept list and added to the suppressed records.

    Returns (kept, suppressed) where:
      - kept is the filtered list of GatedFinding to continue down the pipeline
      - suppressed is a list of dicts suitable for 2c-suppressed.json
    """
    if not gated:
        return gated, []

    kept: list[GatedFinding] = []
    suppressed: list[dict] = []

    for gf in gated:
        if gf.verdict != "PASS":
            kept.append(gf)
            continue

        match: SuppressionMatch | None = None
        for sig_fn in _SIGNATURES:
            match = sig_fn(gf.finding, meta)
            if match is not None:
                break

        if match is None:
            kept.append(gf)
        else:
            suppressed.append({
                "finding_number": match.finding_number,
                "signature": match.signature_name,
                "reason": match.reason,
                "matched_pattern": match.matched_pattern,
                "defect_snippet": gf.finding.defect[:300],
                "evidence_quote_snippet": match.evidence_quote_snippet,
            })
            print(
                f"  [suppress/{match.signature_name}] finding #{match.finding_number}: "
                f"{match.reason}"
            )

    if suppressed:
        print(f"  Suppressed {len(suppressed)} finding(s) under known-FP precision discipline")

    return kept, suppressed
