# Paperlint — Architecture and Pipeline Design

_Internal design reference for audit and review. This document describes how the system is architected and how the pipeline works — it is not part of the public-facing product._

_Last updated April 23, 2026._

---

## 1. Overview

PaperLint is the data-acquisition and transformation layer at the front of the pipeline. It scrapes open-std.org mailing metadata, downloads papers, and converts them to markdown. After PaperLint populates Postgres, Agora21 runs, then C++ Herald concurrently; PRAGMA also follows. None of these downstream systems ingest the mailing directly — they all read from Postgres.

**Single public repo principle** (Vinnie, Apr 10 huddle): _"Can a user clone the repo and only the repo and replicate the findings? You want the minimum. That from which no single file can be removed and still achieve the result."_

Two modes of operation:

- **Local mode:** JSON files in a workspace directory, no Postgres required. Any user can clone `cppalliance/wg21-paperlint`, run the CLI, and replicate the scrape and conversion steps.
- **Production mode:** Celery task in the Django app (`wg21-website`), Postgres backend.

---

## 2. Repository Layout

tomd is folded into `cppalliance/wg21-paperlint` — no reason to keep it in a separate repo that causes multiple copies and confusion.

```
cppalliance/wg21-paperlint/      (public — users clone this to replicate)
├── tomd/                        # PDF/HTML → Markdown (folded in)
├── paperlint/
│   ├── mailing.py               # Scrapes open-std.org mailing index → metadata JSON
│   ├── extract.py               # Downloads paper, hands local path to tomd
│   ├── pipeline.py              # Discovery → Gate → Summary (LLM eval steps, suspended)
│   ├── storage.py               # Backend abstraction: JSON (default) vs Postgres
│   ├── models.py                # Paper data model (see §4)
│   ├── orchestrator.py          # High-level: fetch → convert → eval
│   ├── docs/
│   │   └── design.md            # This file
│   └── prompts/                 # LLM prompts (hashed for reproducibility)
└── pyproject.toml
```

`cppalliance/wg21-website` (private Django app) imports wg21-paperlint as a Git submodule. The Postgres backend implementation lives in `wg21-website`, not here.

---

## 3. Pipeline Ordering

```
open-std.org mailing
        │
        ▼
 wg21-paperlint: scrape ──► convert (parallel) ──► eval (policy-suspended)
        │                        │                       │
   serial, one             tomd × N papers        LLM × N papers
   HTTP stream             (minutes / mailing)    (available in CLI,
        │                                          not enabled for production)
        ▼
     Postgres
   ┌────┼────┐
   ▼    ▼    ▼
Agora21  C++ Herald  PRAGMA
```

- Scrape is the serial bottleneck: one request stream to open-std.org.
- After scrape, tomd conversion is embarrassingly parallel (minutes for a full mailing). tomd is lightweight — no ML, no OCR — so many workers can run concurrently with low memory overhead.
- **Eval is currently policy-suspended for production use.** The CLI implementation still exists for local and future use. Vinnie, Apr 22 2026: _"We have turned off the evaluation of papers for now because it is not as objective as we would like."_ Vinnie redirected contributors toward the PDF/HTML→markdown conversion and paper-revision diff work. The scrape+convert path runs independently.
- Downstream systems (Agora21, C++ Herald, PRAGMA) read from Postgres — they do not re-scrape the mailing.

---

## 4. Paper Data Model

Canonical Python representation in memory and in the JSON backend:

```python
@dataclass
class Paper:
    document_id: str       # e.g. "P3642R4"
    mailing_id: str        # e.g. "2026-02"
    title: str
    authors: list[str]
    mailing_date: str      # ISO date of the mailing, e.g. "2026-02-15"
    publication_date: str  # ISO date from the paper itself, e.g. "2026-01-15"
    audience: list[str]    # short names: ["LEWG", "SG14"] — no hyphens
    intent: str            # "ask" | "info" (maps to paper_type in open-std)
    url: str               # canonical open-std.org URL
    markdown: str          # output of tomd
    meta_source: str       # "mailing" | "tomd" | "merged"
```

`meta_source` records provenance: `"mailing"` = authoritative from open-std scrape; `"tomd"` = extracted by tomd from the paper body; `"merged"` = both sources agreed.

**Metadata authority rule** (Vinnie, Apr 22 huddle): _"The website should always show what comes from the mailing."_ The mailing index is the source of truth for all fields. tomd extracts metadata present in the source file. After conversion, paperlint applies the scraped mailing metadata as a fallback for missing YAML front-matter fields while preserving fields that tomd extracted from the paper body.

---

## 5. tomd YAML Front-Matter Spec

Fields tomd emits and their canonical forms:

| Field | Correct form | Wrong form |
|---|---|---|
| `intent` | `intent: ask` or `intent: info` | `paper-type: informational` |
| `intent` position | after `date`, before `audience` | any other position |
| `title` | `title: "A Minimal Coroutine..."` (quoted) | `title: A Minimal Coroutine...` |
| Audience values | Short names, no hyphens: `LEWG`, `SG16` | Long names: `LEWG Library Evolution`, `SG-16` |

Canonical field order: `title`, `document`, `date`, `intent`, `audience`, `reply-to`.

Audience normalization: wg21.org displays audience values from open-std metadata but must normalize to short names without hyphens. "EWG Evolution" → "EWG", "SG-16" → "SG16". The tag normalization formula is Will's to define.

tomd's contract: extract what's in the source file. If a field is absent from the source, leave it absent. paperlint owns the mailing-index context and fills missing YAML front-matter fields after tomd returns markdown.

---

## 6. Backend Abstraction

Two concrete backends behind the same Python interface (`storage.py`):

**JSON backend** (default — no external dependencies):
- Workspace directory: `./data/` (configurable)
- One JSON file per paper, one per mailing index
- Markdown stored as `.md` files alongside JSON
- Used for local replication, testing, CI, debugging
- Invocation: `python -m paperlint run 2026-02 --workspace-dir ./data/`

**Postgres backend** (production):
- Implemented in `wg21-website` (private), not in this repo
- Django app calls paperlint functions directly as a Python library — not via subprocess — so paper objects are shared in-memory without serialization overhead
- `storage.py` here defines only the abstract interface

The JSON backend must work without Postgres installed. The Postgres backend must not be required to run paperlint (Vinnie, Apr 22 huddle): _"It has to be in PaperLint because users need to be able to do it. So that means someone needs to be able to clone the PaperLint repo, run the scraper, and get the JSON into a specific directory."_

JSON is preferred over SQLite for the local backend because files are directly inspectable for debugging (Vinnie, Apr 22 huddle): _"if it's JSON, then people can inspect it. It can do double duty as a debug tool."_

---

## 7. Django Integration

How `wg21-website` (private) calls into `cppalliance/wg21-paperlint` (public):

```python
# In wg21-website (private):
from paperlint.orchestrator import convert_one_paper
from paperlint.mailing import fetch_mailing_index

@app.task
def process_mailing(mailing_id: str):
    index = fetch_mailing_index(mailing_id)
    for paper in index.papers:
        convert_one_paper(paper, backend=PostgresBackend(db))
        # eval pipeline suspended; add back when ready
```

wg21-paperlint is installed as a Git submodule. Django imports it as a Python library, not via subprocess.

Mailing polling/scheduling is owned by the consuming application. paperlint exposes explicit mailing fetch and conversion entry points; it does not run a scheduler.

---

## 8. CLI Contracts

Each stage is independently runnable with JSON files as I/O:

```bash
# Fetch and scrape mailing index only
python -m paperlint mailing 2026-02 --workspace-dir ./data/

# Convert all papers to markdown (no LLM, parallel)
python -m paperlint convert 2026-02 --workspace-dir ./data/ [--max-workers 10]

# Run full eval pipeline on one paper (CLI available; production policy-suspended)
python -m paperlint eval 2026-02/P3642R4 --workspace-dir ./data/

# Batch eval all papers in a mailing (CLI available; production policy-suspended)
python -m paperlint run 2026-02 --workspace-dir ./data/ [--max-cap 10]

# tomd standalone (local source file in, markdown out)
python -m tomd.main .paperlint_cache/p3642r4.pdf --outdir ./data/
```

CLI requires `<mailing-id>/<paper-id>` form; bare paper-id or local path returns a clean error (decided in PR #43).

---

## 9. Output Schema and Pipeline Reference

_The following sections are preserved verbatim from the pipeline design reference._

### Pipeline Overview

```
Paper (HTML or PDF via mailing-index URL — local paths are not accepted)
  │
  ▼
Step 0: METADATA (no LLM)
  Input: clean text from `extract_text()` dispatching to tomd's HTML/PDF converters
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
  Method: exact substring match, then whitespace-normalized substring match
  Output: findings retained only when all evidence quotes verify
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

### Evidence Model

Each finding carries an array of evidence — exact quotes from the source document with their locations:

```json
"evidence": [
  {"location": "§16.4.6.17, item (1.1)", "quote": "error category objects (19.5.3.5)"},
  {"location": "§16.4.6.17, item (1.2)", "quote": "time zone database (19.5.3.5)"}
]
```

Each quote is programmatically verified against the source text before reaching the Gate. A finding is dropped if any evidence quote cannot be verified, so the Gate sees only findings whose full evidence set is present in the converted text.

---

### JSON Mode

Every pipeline LLM step uses JSON mode (`response_format: {"type": "json_object"}` on OpenRouter). Models return structured JSON parsed with `json.loads()`. `_parse_json()` tolerates minor formatting issues for robustness.

**OpenRouter fence handling:** OpenRouter may wrap responses in code fences. `_strip_fences()` removes fences before parsing.

---

### Text Extraction

| Source | Function | Library | Used by |
|--------|----------|---------|---------|
| HTML | `extract_text()` → `tomd.lib.html.convert_html()` | home-grown tomd converter | Metadata, Discovery, Gate |
| PDF | `extract_text()` → `tomd.lib.pdf.convert_pdf()` | home-grown tomd converter | Metadata, Discovery, Gate |

Text extraction produces clean text. Metadata and LLM stages receive the same extracted text stored as `paper.md`.

---

### Models

| Step | Model | Provider | Mode |
|------|-------|----------|------|
| Metadata | _(none)_ | — | — |
| Discovery | Opus 4.6 | OpenRouter | JSON + thinking |
| Gate | Opus 4.6 | OpenRouter | JSON + thinking |
| Summary | Sonnet 4.6 | OpenRouter | JSON |

All LLM calls route through OpenRouter. Paper fetch uses `requests` with a timeout.

---

### Output Schema

#### Per-paper: `evaluation.json`

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

#### Per-mailing: `index.json` (batch mode only)

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

#### Intermediate artifacts (per-paper, for debugging)

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

### Versioning

Each evaluation carries two identifiers:
- **`paperlint_sha`** — git commit hash. Tracks which code produced this.
- **`prompt_hash`** — SHA-256 (truncated) of **all** `prompts/**/*.md` plus `rubric.md`. Changes when any prompt or rubric content changes.

Rerun rule: prompt_hash changed → full rerun. Unchanged → skip.

---

### Invocation

```bash
python -m paperlint eval 2026-02/P3642R4 --workspace-dir ./output/
python -m paperlint run 2026-02 --workspace-dir ./data/ --max-cap 50 --max-workers 10
python -m paperlint mailing 2026-02 --workspace-dir ./data/
```

---

### Dependencies

```
openai             # OpenRouter API (all model calls)
python-dotenv      # .env loading
tomd               # Bundled PDF/HTML-to-Markdown converter
beautifulsoup4     # HTML parsing (mailing page scraper)
requests           # HTTP (paper fetching, mailing scraper)
```

---

### Environment

```
OPENROUTER_API_KEY=sk-or-...
# Optional:
# OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

---

### Known Limitations

- **Context window:** Papers exceeding ~200K tokens cannot be processed in a single Discovery call.
- **PDF conversion:** tomd is under active development. It handles the target WG21 paper formats directly, but some papers still need converter improvements before their markdown output is fully accurate.
- **Evaluation non-determinism:** The scrape and tomd conversion stages are deterministic. The LLM evaluation stages may produce different candidate findings across runs; the Gate is intended to improve precision, but candidate coverage can vary.

---

### Prompts

| Stage | File | Role |
|-------|------|------|
| Discovery | `prompts/1-discovery.md` | Find every mechanically verifiable defect |
| Gate | `prompts/2-verification-gate.md` | Reject everything that isn't a real defect |
| Summary | `prompts/3-evaluation-writer.md` | Emit a short summary JSON only |
| Rubric | `rubric.md` | Failure modes across 4 axes |
| Extensions | `prompts/extensions/*.md` | Hashed with prompts; optional future wiring |

The prompts are the product. The orchestrator is the plumbing.

---

## 10. Open Questions

Decisions not yet finalized as of Apr 23, 2026:

- **GitHub issues per paper:** Where does per-paper issue tracking live once eval ships? `wg21.link/PXXXX/github` works as a URL pattern; where this is hosted and how paperlint links to it is unresolved.
