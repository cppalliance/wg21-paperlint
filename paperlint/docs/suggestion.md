# Suggestions for Paperlint maintainers

## 1. Proposed enhancements

Ways to improve precision, clarity, and robustness as the tool matures. **Subsections are ordered from lower to higher effort** (roughly: docs first, then localized code/schema, then pipeline architecture).

### 1.1 Document quote verification and extraction limits (then tighten heuristics)

- **Gap:** `step_verify_quotes` (`paperlint/orchestrator.py` ~381–421) only checks that each quote appears as a substring (exactly or after whitespace normalization). It does not prove the defect text is true, that the quote is the _intended_ occurrence, or that extraction matches the author’s PDF visually.
- **Reason:** Users often read “verified” as “ground truth.” In reality, **verified ⊆ extracted text**. Short quotes can match many places; `str.find` uses the **first** match, so `extracted_char_start` may not match the section named in `location`. PDF extraction can drop or reorder content. Without explicit docs, false positives and false trust are both more likely. After the README is clear, **optional code heuristics** (minimum quote length, flagging quotes that appear more than once) are a small incremental cost for a meaningful drop in weakly anchored findings.
- **Proposal:** **Phase A (low effort):** In README, define **verified** precisely and list limits (extraction, substring-only, first-match behavior for EXACT path; NORM path does not set char offsets ~400–402). **Phase B (moderate):** In `step_verify_quotes`, add configurable rules—e.g. reject evidence shorter than _N_ characters, or warn/reject when `source_text.count(quote) > 1` unless discovery later supplies disambiguators. Add tests for each rule. Tune _N_ against real papers to avoid nuking valid short quotes.

### 1.2 Richer gate context (local windows or second pass)

- **Gap:** `step_gate` sends the **entire** `clean_text` inside `<paper>…</paper>` plus all candidates in one request (`orchestrator.py` ~474–478). There is no second model pass that only re-evaluates first-round PASS items.
- **Reason:** Very long papers increase token load and dilute attention to the neighborhood of each quote. A mistaken PASS with `judgment: false` is still published. Quote-local context is partially supported by data: after **EXACT** match, `extracted_char_start` / `extracted_char_end` are set (~393–395); **NORM** matches do not set offsets, so windowing is incomplete until NORM is improved or those findings stay on full text.
- **Proposal:** **Option A — Windows:** For each finding (or batched by overlap), build `clean_text[max(0, start−k):min(len, end+k)]` and call the gate with that excerpt plus metadata, or prepend labeled excerpts to a shorter global context. **Option B — Second pass:** After the first gate, run again with a stricter system prompt only on findings with `verdict == PASS`, and require consensus (both PASS) or downgrade to REJECT/REFER. Implement behind flags (e.g. CLI) to control cost. Start with Option A for EXACT-only evidence if NORM mapping is deferred.

### 1.3 Golden-set regression for prompts

- **Gap:** There is no checked-in set of papers with **human-labeled** expected outcomes (e.g. which findings should PASS the gate, or precision/recall targets) and no automated comparison when `prompt_hash` or models change.
- **Reason:** Prompt edits are high-leverage but opaque: a small wording change can raise false positives or false negatives. Without a frozen corpus and a repeatable scorer, regressions appear only in ad hoc user reports. Cost and API keys make full CI on every PR optional, but the _absence_ of any baseline makes iteration risky.
- **Proposal:** Curate a **small** golden set (e.g. 5–15 papers) and store expected artifacts or labels (could be “allowed finding ids” or human PASS/REJECT per synthetic finding). Add a script `scripts/check_golden.py` or `pytest` integration that runs the pipeline (or gate-only with canned inputs) and compares to baselines. Run on **release**, on **prompt/rubric edits**, or via **workflow_dispatch** / scheduled CI so it is not mandatory on every push. Record `prompt_hash` in the report when results drift.

### 1.4 Chunking for very long papers

- **Gap:** Discovery and gate assume a **single** user message containing the full extracted document (within model context). There is no merge/dedupe layer for overlapping discovery chunks.
- **Reason:** Papers approaching context limits may truncate, error, or receive shallow analysis. Splitting nothing is simpler but caps which mailings can be processed reliably and may unevenly stress cost.
- **Proposal:** **Discovery:** Split `clean_text` into overlapping chunks (by character budget or §-aware boundaries), run discovery per chunk, merge findings and **dedupe** by normalized quote + category. **Gate:** Prefer quote-local windows (§1.2) before full chunking of the gate; if the full paper still does not fit, batch findings with shared context windows. Add integration tests on a synthetic long document. Expect engineering on dedupe and cross-chunk contradictions (optional final holistic pass).

### 1.5 Optional multimodal grounding

- **Gap:** The pipeline uses **one** plain-text stream from `extract_text()` for verification and gate. HTML structure (ins/del) and PDF **rendered** layout are not inputs to the gate.
- **Reason:** Extraction can misrepresent strikethrough, figures, or “ill-formed” blocks; some committee readers reason from the PDF. Vision or HTML snippets could reduce certain false positives or clarify author intent—at the cost of modality, API complexity, and pinning “verified” to text vs pixels.
- **Proposal:** Treat as **later phase.** If pursued: (1) keep **substring verification on `clean_text`** as the default contract unless the product explicitly allows vision-only findings; (2) experiment with **cropped HTML** around a finding’s location for the gate; (3) or **render PDF pages** (PyMuPDF) to images for a **second opinion** on REFER or PASS-only review—not necessarily for every paper. Select a vision-capable model and budget; prototype on a handful of failure cases from production runs.

---

## 2. Corrections and maintenance

Concrete fixes: bugs, documentation drift, missing tests, and output gaps in the current codebase.

### 2.1 No automated tests

- **Issue:** There is no `tests/` tree or `pytest` suite; behavior is only exercised by manual runs.
- **Reason:** Prompt edits, gate JSON shape changes, or refactors in quote verification / assembly can regress silently.
- **Suggestion:** Add focused tests (`step_verify_quotes`, gate `judgment` coercion, `verdict_map` / duplicate handling, assembly) under root `tests/` with `pytest` as a dev dependency.

### 2.2 Internal design doc out of sync with code

- **Issue:** `paperlint/docs/design.md` describes models, thinking, intermediate files, and `evaluation.json` in ways that do not match `paperlint/orchestrator.py` (e.g. summary step model, `3-eval.json`, finding shape).
- **Reason:** Auditors and contributors rely on that doc for behavior and cost assumptions.
- **Suggestion:** Align `design.md` with `step_metadata`, `step_discovery`, `step_summary_writer` (~561+), `step_gate` (~462+), and assembly (~723–773).

### 2.3 Misleading `extract.py` module docstring

- **Issue:** `paperlint/extract.py` (~10–15) claims discovery uses raw bytes / Citations API and that extraction is metadata-only.
- **Reason:** `extract_text()` output actually feeds metadata, discovery, quote verification, and gate via `run_paper_eval`.
- **Suggestion:** Rewrite the docstring to describe the full pipeline use of one extracted string.

### 2.4 Paper download has no HTTP timeout

- **Issue:** `paperlint/orchestrator.py` — `fetch_paper` (~628–656) uses `urllib.request.urlretrieve` without a timeout.
- **Reason:** Stuck connections can hang runs indefinitely; `mailing.py` already uses bounded timeouts.
- **Suggestion:** Use `urlopen(..., timeout=...)` or `requests.get(..., timeout=...)`; keep cache and year-retry logic.

### 2.5 Empty evidence lists in quote verification

- **Issue:** `paperlint/orchestrator.py` — `step_verify_quotes` (~381–421) keeps a finding when `all(ev.verified for ev in f.evidence)`; for `evidence == []`, `all([])` is true in Python.
- **Reason:** Findings could reach the gate with no quoted evidence.
- **Suggestion:** Drop zero-evidence findings or treat as invalid; align `prompts/1-discovery.md` if quotes must always be present.

### 2.6 Redundant logic in `step_verify_quotes`

- **Issue:** Same function (~389–407) updates `all_verified` while the keep/drop branch uses `all(ev.verified for ev in f.evidence)`.
- **Reason:** Redundant state obscures intent and looks unfinished.
- **Suggestion:** Remove `all_verified` or use one predicate only.

### 2.7 Unpinned runtime dependencies

- **Issue:** `pyproject.toml` and `requirements.txt` list packages without version ranges.
- **Reason:** Reproducible CI and bisecting environment-specific failures is harder.
- **Suggestion:** Add compatible bounds or adopt a lockfile after a known-good freeze.

### 2.8 REFER outcomes omitted from `evaluation.json`

- **Issue:** `paperlint/orchestrator.py` — assembly (~720–773) writes only **PASS** findings to `evaluation.json`; **REFER** appears in `2-gate.json` only.
- **Reason:** Consumers that read only the flat deliverable miss “needs human review” and referred counts.
- **Suggestion:** Add e.g. `findings_referred` / `findings_referred_count` (or a documented sidecar) without mixing REFER into the PASS `findings` array; document in README.

---

## Suggested priority

- **§1 (enhancements):** Follow subsection order when possible — **§1.1 Phase A** first (README-only), then **§1.1 Phase B** (quote heuristics + tests), **§1.2**, then **§1.3** once a golden set exists, and **§1.4–§1.5** when length or extraction is the measured bottleneck.

- **§2 (maintenance):** Harden with **§2.1, §2.4, §2.5**, then **§2.2, §2.3, §2.8**, and **§2.6–§2.7** as cleanup allows.

Blend §1 and §2 according to maintainer capacity; README and timeout fixes pay off quickly alongside **§1.1 Phase A**.
