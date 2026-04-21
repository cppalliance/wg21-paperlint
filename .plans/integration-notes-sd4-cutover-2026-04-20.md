# Integration notes — SD-4 rubric cutover

Checklist for the integration stage after prompt review is complete. Nothing here is prompt-writing; all of it is orchestrator, file-swap, or calibration work.

## 1. Archive existing prompts

Move before overwriting:

```
paperlint/prompts/1-discovery.md           → paperlint/prompts/archive/1-discovery-<cutover-date>.md
paperlint/prompts/2-verification-gate.md   → paperlint/prompts/archive/2-verification-gate-<cutover-date>.md
paperlint/prompts/3-evaluation-writer.md   → paperlint/prompts/archive/3-evaluation-writer-<cutover-date>.md
paperlint/rubric.md                        → paperlint/prompts/archive/rubric-<cutover-date>.md
```

Also consider archiving `paperlint/suppress.py`'s signature-class corpus if the new rubric's scope makes them unreachable (intra-word spacing, TOC location, bracketed identifier wrap — all extraction-artifact classes, still relevant for content-gap evaluation but check).

## 2. Install new prompts

Promote drafts from `.plans/` to `prompts/` and `rubric.md`:

```
.plans/discovery-prompt-sd4-draft-2026-04-20.md        → paperlint/prompts/1-discovery.md
.plans/gate-prompt-sd4-draft-2026-04-20.md             → paperlint/prompts/2-verification-gate.md
.plans/evaluation-writer-prompt-sd4-draft-2026-04-20.md → paperlint/prompts/3-evaluation-writer.md
.plans/rubric-sd4-draft-2026-04-20.md                  → paperlint/rubric.md
```

## 3. Update orchestrator JSON-schema strings

Three hardcoded `json_schema` strings in `orchestrator.py` emit the current finding/verdict shape. Replace each with the new shape below. `response_format={"type": "json_object"}` stays as-is; no full JSON-Schema enforcement added (same architecture).

### 3a. `step_discovery` JSON schema

```json
{
  "paper_type": "proposal | ts | white_paper | working_draft | wording_clarification | other",
  "references": [
    {
      "id": "r1",
      "location": "section number, heading, paragraph",
      "text": "exact text from the paper, character-for-character"
    }
  ],
  "findings": [
    {
      "number": 1,
      "question": "Q1 | Q2 | Q3 | Q4 | Q5 | Q6 | Q7 | Q8 | U",
      "title": "short description",
      "requirement": "SD-4 source text, quoted verbatim from rubric.md",
      "gap": "what the paper does not do — one sentence",
      "present_summary": "prose description of what was found, or 'no treatment found after thorough search' when pure absence",
      "references": ["r1"],
      "would_pass": "what a passing treatment would include — one sentence"
    }
  ]
}
```

If `paper_type` is not `"proposal"`, `findings` and `references` must be `[]`.

The orchestrator resolves each `references[i].text` to `extracted_char_start` and `extracted_char_end` against `paper.md` after the LLM call (same pattern as v1's evidence-quote resolution). The LLM is not asked to count characters.

Findings without references (pure absence — the paper does not address the question at all) have an empty `references` array. Findings citing weak or partial treatment list the relevant reference IDs. Same content cited by multiple findings appears once in the references collection.

### 3b. `step_gate` JSON schema

```json
{
  "verdicts": [
    {
      "finding_number": 1,
      "question": "Q1 | Q2 | Q3 | Q4 | Q5 | Q6 | Q7 | Q8 | U",
      "verdict": "PASS | REJECT | REFER",
      "reason": "one sentence — treatment-search confirming shortfall, rejection reason, or uncertainty",
      "judgment": false
    }
  ]
}
```

### 3c. Evaluation writer JSON schema

```json
{
  "summary": "characterization of findings (e.g., 'Falls short on Q1 and Q7') or 'No SD-4 shortfalls found.' if zero findings — does not summarize the paper",
  "references": [
    {
      "id": "r1",
      "location": "section number, heading, paragraph",
      "text": "exact text from the paper",
      "extracted_char_start": 12345,
      "extracted_char_end": 12400
    }
  ],
  "findings": [
    {
      "question": "Q1 | Q2 | Q3 | Q4 | Q5 | Q6 | Q7 | Q8 | U",
      "title": "short description",
      "gap": "what the paper does not do — one sentence",
      "references": ["r1"],
      "would_pass": "what a passing treatment would include — one sentence"
    }
  ]
}
```

Carry `question`, `title`, `gap`, `references` (IDs), and `would_pass` through from the gated findings. Carry the `references` collection (with char offsets) through unchanged. Do not regenerate any of these.

## 4. Orchestrator flow considerations

- **Scope gate.** Discovery returns `paper_type` at top level. If `paper_type != "proposal"`, short-circuit the pipeline after discovery: skip gate, skip summary writer, emit a terminal evaluation with `summary = "<paper-type> — out of scope for this rubric"` and `findings = []`. Avoids wasted LLM calls and keeps the output-file contract consistent.
- **Co-occurrence enforcement.** The rubric's co-occurrence rules (Q1→Q3, Q5→Q6, Q7→Q8) are instructions to the LLM. Belt-and-suspenders: after gate, post-process verdicts to suppress the subsumed pair if both passed. Low priority; the prompts should handle it, but a deterministic check is cheap insurance.

## 5. Specimens and calibration

We have no labeled corpus yet for gap-style findings. The current `rubric.md` + `suppress.py` corpus targets extraction-artifact defects, which is a different class. Cold-start plan:

- First regen after cutover on the 2026-02 mailing. Expected behavior: findings are gaps against Q1–Q8, not typography/extraction defects. Expect aggregate finding count to shift significantly (direction unknown — could go up or down depending on how many papers have all 8 pillars covered).
- Reviewer feedback after first regen becomes the calibration signal. Expect triage to flag: questions raised too aggressively (gate not strict enough), questions missed (discovery prompt's thorough-search instruction under-applied), and co-occurrence double-fires (prompt co-occurrence rule not followed).
- Consider a small hand-curated corpus of 4–6 papers with known pass/fail against each of the 8 questions. Use as a regression baseline after every prompt edit.

## 6. What does not change

- `orchestrator.py` pipeline stages (metadata → discovery → quote verification → gate → summary → assembly → output). Same stages, same coordination.
- `extract.py` (docling + pymupdf fallback, HTML extraction). Paper form unchanged.
- Output contract (per-paper `{paper_id}/evaluation.json` + `{paper_id}/paper.md` with character offsets). Consumed by Will Pak for wg21-website integration — contract preserved.
- Suppression layer (`suppress.py`). The three deterministic signature classes are orthogonal to the SD-4 rubric and stay live.
- CPPA LLM convention (OpenRouter via `openai` SDK). No SDK change.

## 7. What may break on first run

- `_parse_json` fallback chain has been battle-tested on the old schema. New schema has similar shape (top-level object with `findings` array) so no structural risk, but watch for field-name typos in the schema strings.
- Thinking budgets (`THINKING_BUDGET["discovery"]`, etc.) were tuned for the old rubric. New rubric asks for different cognitive work (gap-finding vs defect-finding) and may need rebalancing. Monitor.
- The old rubric's 4 axes mapped to `category` field values (e.g., "1.2"). New rubric uses `Q1`–`Q8` and `U`. Any downstream consumers that grep for the old category codes (reviewer feedback scripts, reports, reviewer-response tooling) need updating.
