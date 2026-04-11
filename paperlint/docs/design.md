# Paperlint — Pipeline Design

_Internal design reference for audit and review. This document describes how the pipeline works — it is not part of the public-facing product._

_Last updated April 11, 2026._

---

## Pipeline Overview

```
Paper (HTML or PDF, by number or path)
  │
  ▼
Step 0: METADATA
  Model: Sonnet 4.6 via OpenRouter (JSON mode)
  Input: clean text — extract_html() for HTML, extract_pdf() for PDF
  Output: JSON {title, authors, audience, paper_type, abstract}
  │
  ▼
Step 1: DISCOVERY
  Model: Opus 4.6 via Anthropic API (Citations enabled)
  Input: raw paper — HTML as text/plain, PDF as application/pdf base64
  Prompt: prompts/1-discovery.md + rubric.md
  Output: free-form markdown with citation anchors from API
  Note: only step that is NOT JSON mode (Citations API constraint)
  │
  ▼
Step 1b: EXTRACTOR
  Model: Sonnet 4.6 via OpenRouter (JSON mode)
  Input: Discovery free-form output
  Output: JSON array of findings {number, title, category, location,
          quoted_text, defect, correction, axiom}
  │
  ▼
Step 1c: CITATION MAPPING (compute, no model)
  Input: Extractor findings + Discovery block spans
  Output: findings with attached citation positions (start_char, end_char)
  Method: anchored regex on #### Finding N: headings, block-start rule
  Validated: 581/581 headings across 78 production runs, zero false positives
  │
  ▼
Step 2: GATE
  Model: Opus 4.6 via OpenRouter (JSON mode + thinking)
  Input: JSON findings + paper text for context
  Prompt: prompts/2-verification-gate.md
  Output: JSON verdicts {finding_number, verdict, reason}
  │
  ▼
Step 3: EVALUATION WRITER
  Model: Opus 4.6 via OpenRouter (JSON mode + thinking)
  Input: PASSed findings + metadata
  Prompt: prompts/3-evaluation-writer.md
  Output: JSON {summary, findings[{location, description}]}
  Note: does NOT produce references — those come from Step 1 citations
  │
  ▼
Step 4: ASSEMBLY (compute, no model)
  Input: metadata (0) + citations (1c) + verdicts (2) + eval (3)
  Output: evaluation.json — single deliverable file per paper
```

---

## Provenance

Discovery always receives the **original source format**:
- HTML papers: `media_type: "text/plain"`, raw HTML
- PDF papers: `media_type: "application/pdf"`, base64-encoded bytes

The Citations API returns character-span references into the source as provided. These reference the ground truth document — not a conversion or derivative.

Text extraction (`extract_text()`) is used **only** for the metadata step where Sonnet needs clean text to read front matter. It is never fed to Discovery.

---

## JSON Mode

Every pipeline step except Discovery uses JSON mode (`response_format: {"type": "json_object"}` on OpenRouter). Models return structured JSON parsed with `json.loads()`. No regex parsing of LLM output anywhere in the pipeline.

**OpenRouter fence handling:** OpenRouter wraps Anthropic JSON mode responses in code fences. `strip_openrouter_json()` removes fences before parsing. Handles both fenced and unfenced responses.

**Discovery exception:** The Citations API requires free-form text output to attach citation anchors. The Extractor (Step 1b) converts Discovery's free-form output to structured JSON via a model call — a model reads model output, not regex.

---

## Models

| Step | Model | Provider | Mode | Why |
|------|-------|----------|------|-----|
| Metadata | Sonnet 4.6 | OpenRouter | JSON | Cheap, fast, reads front matter |
| Discovery | Opus 4.6 | Anthropic | Citations + thinking | Needs Citations API for provenance |
| Extractor | Sonnet 4.6 | OpenRouter | JSON | Structured extraction, not reasoning |
| Gate | Opus 4.6 | OpenRouter | JSON + thinking | Hard reasoning — "find the author's reason" |
| Eval Writer | Opus 4.6 | OpenRouter | JSON + thinking | Synthesis — writes what authors read |

---

## Output Schema

### Per-paper: `evaluation.json`

```json
{
  "schema_version": "1",
  "paperlint_sha": "abc123def456",
  "paper": "P3642R4",
  "title": "Carry-less product: std::clmul",
  "authors": ["Jan Schultke"],
  "audience": "LEWG",
  "paper_type": "wording",
  "abstract": "Summary of what the paper proposes...",
  "generated": "2026-04-11T01:30:00Z",
  "model": "claude-opus-4-6",
  "findings_discovered": 8,
  "findings_passed": 6,
  "findings_rejected": 2,
  "summary": "Evaluation summary...",
  "findings": [
    {
      "location": "§5.2",
      "description": "plain text description of the defect",
      "reference_number": 1
    }
  ],
  "references": [
    {
      "number": 1,
      "cited_text": "exact text from paper",
      "start_char": 12345,
      "end_char": 12400
    }
  ]
}
```

### Per-mailing: `index.json` (batch mode only)

```json
{
  "schema_version": "1",
  "paperlint_sha": "abc123def456",
  "mailing_id": "2026-02",
  "generated": "2026-04-11T06:00:00Z",
  "total_papers": 81,
  "succeeded": 80,
  "failed": 1,
  "rooms": {
    "LEWG": {
      "papers": ["P3642R4", "P2929R2"],
      "total_findings": 11
    }
  },
  "papers": [
    {
      "paper": "P3642R4",
      "title": "Carry-less product: std::clmul",
      "audience": "LEWG",
      "findings_passed": 6,
      "findings_discovered": 8
    }
  ]
}
```

### Intermediate artifacts (per-paper, for debugging)

```
{output_dir}/{paper_id}/
├── evaluation.json        # the deliverable
├── meta.json              # Step 0: metadata
├── 1-discovery-raw.md     # Step 1: Discovery free-form output
├── 1-discovery-debug.txt  # Step 1: citation debug info
├── 2-findings.json        # Step 1b: structured findings
├── 3-gate.json            # Step 2: verdicts
└── 4-eval.json            # Step 3: Eval Writer output
```

---

## Invocation

```bash
# Single paper
python -m paperlint eval P3642R4 --output-dir ./output/

# Single paper from local file
python -m paperlint eval ./papers/p3642r4.html --output-dir ./output/

# Batch — entire mailing
python -m paperlint run 2026-02 --output-dir ./data/ --max-cap 50 --max-processes 10

# All OpenRouter (no Anthropic API needed, no citations)
python -m paperlint eval P3642R4 --output-dir ./output/ --all-openrouter
```

---

## Dependencies

```
anthropic          # Anthropic API (Discovery + Citations)
openai             # OpenRouter API (Gate, Eval Writer, Metadata, Extractor)
python-dotenv      # .env loading
pymupdf            # PDF text extraction (metadata step only)
beautifulsoup4     # HTML parsing (mailing page scraper)
requests           # HTTP (paper fetching, mailing scraper)
```

---

## Environment

```
ANTHROPIC_API_KEY=sk-ant-...     # Discovery (Anthropic Citations API)
OPENROUTER_API_KEY=sk-or-...     # All other steps (OpenRouter)
```

---

## Known Limitations

- **Context window:** Papers exceeding ~200K tokens cannot be processed by Discovery in a single call.
- **PDF metadata:** `pymupdf` text extraction is good but not perfect on all WG21 PDF formats.
- **Non-determinism:** Same paper run twice may produce different findings. Discovery's recall varies. The Gate provides precision consistency — what passes is reliably correct, but the set of candidates varies.
- **Citation coverage:** Not all Discovery runs produce API citations. When citations are absent, the Extractor's `quoted_text` field provides fallback provenance.

---

## Prompts

| Stage | File | Role |
|-------|------|------|
| Discovery | `prompts/1-discovery.md` | Find every mechanically verifiable defect |
| Gate | `prompts/2-verification-gate.md` | Challenge findings — find the author's reason |
| Eval Writer | `prompts/3-evaluation-writer.md` | Assemble findings into evaluation |
| Rubric | `rubric.md` | 30 failure modes across 4 axes |

The prompts are the product. The orchestrator is the plumbing.
