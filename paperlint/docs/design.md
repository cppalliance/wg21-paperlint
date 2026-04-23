# Paperlint — Pipeline Design

_Internal design reference for audit and review. This document describes how the pipeline works — it is not part of the public-facing product._

_Last updated April 23, 2026._

---

## Pipeline Overview

```
Paper (HTML or PDF via mailing-index URL — local paths are not accepted)
  │
  ▼
Step 0: METADATA (no LLM)
  Input: clean text — extract_html() for HTML, extract_pdf() for PDF
  Source: open-std.org mailing index JSON (authoritative title, authors, subgroup,
          paper_type, canonical URL). No Sonnet/metadata LLM call.
  Output: PaperMeta persisted as meta.json; same extract drives Discovery/Gate text.
  │
  ▼
Step 1: DISCOVERY
  Model: Opus 4.6 via OpenRouter (JSON mode + thinking)
  Input: clean extracted text
  Prompt: prompts/1-discovery.md + rubric.md (+ prompts/**/*.md hashed with rubric)
  Multi-pass (default 3, CLI `--discovery-passes N`): pass 1 runs a full discovery
  call. Passes 2..N append a user-message block listing prior findings (category,
  title, first-evidence location + quote excerpt) and instruct the model to return
  only *additional* defects. Each pass response is merged into an accumulator;
  duplicates are dropped using a key on `(category.lower(), first_location.lower(),
  normalized_first_quote_prefix)` (whitespace-collapsed, lowercased, first 120 chars
  of the first evidence quote). Final list is renumbered 1..N before quote
  verification and the gate.
  Output: JSON {findings: [{number, title, category, defect, correction,
          axiom, evidence: [{location, quote}]}]}
  │
  ▼
Step 1b: QUOTE VERIFICATION (compute, no model)
  Input: findings + source text
  Method: substring match — each evidence quote verified against source
  Output: findings with unverifiable evidence dropped
  │
  ▼
Step 2: GATE
  Model: Opus 4.6 via OpenRouter (JSON mode + thinking)
  Input: verified findings + paper text for context
  Prompt: prompts/2-verification-gate.md
  Output: JSON verdicts {finding_number, verdict, reason}
  │
  ▼
Step 2c: KNOWN-FP SUPPRESSION (compute, post-gate)
  Input: gated findings → drops PASS findings matching heuristic signatures.
  Output: updated gated list + 2c-suppressed.json audit trail
  │
  ▼
Step 3: SUMMARY WRITER (LLM)
  Model: Claude Sonnet 4.6 via OpenRouter (JSON mode)
  Input: metadata + count of PASS findings after suppression
  Prompt: prompts/3-evaluation-writer.md (append-only summary JSON schema)
  Output: JSON {"summary": "..."} — **findings list is assembled in Python**, not by the model
  │
  ▼
Step 4: ASSEMBLY (compute, no model)
  Input: metadata + verified evidence + verdicts + suppression + summary string
  Output: evaluation.json — single deliverable file per paper
```

---

## Evidence Model

Each finding carries an array of evidence — exact quotes from the source document with their locations:

```json
"evidence": [
  {"location": "§16.4.6.17, item (1.1)", "quote": "error category objects (19.5.3.5)"},
  {"location": "§16.4.6.17, item (1.2)", "quote": "time zone database (19.5.3.5)"}
]
```

Each quote is programmatically verified as a substring of the source text before reaching the Gate. Findings with no verifiable evidence are dropped automatically — the Gate never sees them.

---

## JSON Mode

Every pipeline LLM step uses JSON mode (`response_format: {"type": "json_object"}` on OpenRouter). Models return structured JSON parsed with `json.loads()`. `_parse_json()` tolerates minor formatting issues for robustness.

**OpenRouter fence handling:** OpenRouter may wrap responses in code fences. `_strip_fences()` removes fences before parsing.

---

## Text Extraction

| Source | Function | Library | Used by |
|--------|----------|---------|---------|
| HTML | `extract_html()` | `html.parser` (stdlib) | Metadata, Discovery, Gate |
| PDF | `extract_pdf()` | docling (preferred), pymupdf fallback | Metadata, Discovery, Gate |

Text extraction produces clean text. Metadata and LLM stages receive the same extracted text stored as `paper.md`.

---

## Models

| Step | Model | Provider | Mode |
|------|-------|----------|------|
| Metadata | _(none)_ | — | — |
| Discovery | Opus 4.6 | OpenRouter | JSON + thinking |
| Gate | Opus 4.6 | OpenRouter | JSON + thinking |
| Summary | Sonnet 4.6 | OpenRouter | JSON |

All LLM calls route through OpenRouter. Paper fetch uses `requests` with a timeout.

---

## Output Schema

### Per-paper: `evaluation.json`

```json
{
  "schema_version": "1",
  "paperlint_sha": "abc123def456",
  "prompt_hash": "f25b0f1067fd",
  "paper": "P3642R4",
  "title": "Carry-less product: std::clmul",
  "authors": ["Jan Schultke"],
  "audience": "LEWG",
  "paper_type": "proposal",
  "generated": "2026-04-12T...",
  "model": "anthropic/claude-opus-4.6",
  "findings_discovered": 16,
  "findings_passed": 9,
  "findings_rejected": 7,
  "summary": "Evaluation summary...",
  "findings": [
    {
      "location": "§5.2",
      "description": "plain text description of the defect",
      "category": "2.5",
      "correction": "what it should say",
      "references": [1, 2]
    }
  ],
  "references": [
    {
      "number": 1,
      "location": "§5.2",
      "quote": "exact text from paper",
      "verified": true,
      "extracted_char_start": 120,
      "extracted_char_end": 180
    }
  ]
}
```

`pipeline_status` is one of `complete`, `failed`, or `partial` when present on degraded runs.

### Per-mailing: `index.json` (batch mode only)

```json
{
  "schema_version": "1",
  "paperlint_sha": "abc123def456",
  "prompt_hash": "f25b0f1067fd",
  "mailing_id": "2026-02",
  "generated": "2026-04-12T...",
  "total_papers": 81,
  "succeeded": 78,
  "failed": 3,
  "partial": 2,
  "rooms": {
    "LEWG": {"papers": ["P3642R4"], "total_findings": 9}
  },
  "papers": [
    {"paper": "P3642R4", "audience": "LEWG", "findings_passed": 9, "findings_discovered": 16}
  ]
}
```

`succeeded` counts papers whose `pipeline_status` is `complete`. `failed` counts HTTP/exceptions plus `pipeline_status` of `failed` or `partial`. `partial` is the count of papers that stopped in `partial` status.

### Intermediate artifacts (per-paper, for debugging)

```
{workspace_dir}/{paper_id}/
├── evaluation.json        # the deliverable
├── meta.json              # Step 0: metadata (from mailing index)
├── paper.md               # extracted text (char-offset ground truth)
├── 1-findings.json        # Step 1: discovery findings with evidence
├── 2-gate.json            # Step 2: verdicts
└── 2c-suppressed.json     # Step 2c: suppressed PASS findings (audit)
```

---

## Versioning

Each evaluation carries two identifiers:
- **`paperlint_sha`** — git commit hash. Tracks which code produced this.
- **`prompt_hash`** — SHA-256 (truncated) of **all** `prompts/**/*.md` plus `rubric.md`. Changes when any prompt or rubric content changes.

Rerun rule: prompt_hash changed → full rerun. Unchanged → skip.

---

## Invocation

```bash
python -m paperlint eval 2026-02/P3642R4 --workspace-dir ./output/
python -m paperlint run 2026-02 --workspace-dir ./data/ --max-cap 50 --max-workers 10
python -m paperlint mailing 2026-02 --workspace-dir ./data/
```

---

## Dependencies

```
openai             # OpenRouter API (all model calls)
python-dotenv      # .env loading
pymupdf            # PDF text extraction (fallback)
docling            # PDF structure-aware extraction (preferred)
beautifulsoup4     # HTML parsing (mailing page scraper)
requests           # HTTP (paper fetching, mailing scraper)
```

---

## Environment

```
OPENROUTER_API_KEY=sk-or-...
# Optional:
# OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

---

## Known Limitations

- **Context window:** Papers exceeding ~200K tokens cannot be processed in a single Discovery call.
- **PDF extraction:** docling / pymupdf quality varies by WG21 PDF toolchain.
- **Non-determinism:** Same paper run twice may produce different findings. The Gate provides precision consistency — what passes is reliably correct, but the set of candidates varies.
- **Quote verification:** Substring matching with whitespace normalization; OCR PDFs may still mismatch visual text.

---

## Prompts

| Stage | File | Role |
|-------|------|------|
| Discovery | `prompts/1-discovery.md` | Find every mechanically verifiable defect |
| Gate | `prompts/2-verification-gate.md` | Reject everything that isn't a real defect |
| Summary | `prompts/3-evaluation-writer.md` | Emit a short summary JSON only |
| Rubric | `rubric.md` | Failure modes across 4 axes |
| Extensions | `prompts/extensions/*.md` | Hashed with prompts; optional future wiring |

The prompts are the product. The orchestrator is the plumbing.
