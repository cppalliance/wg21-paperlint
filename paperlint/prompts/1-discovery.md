# Discovery

_For each in-scope rubric question, determine whether it applies to this paper. If it applies, determine whether the paper answers it. If the paper answers it, produce the evidence: a quoted passage from the paper._

---

## Scope

Currently one question is in scope: **Q1**. Consult `rubric.md` for the question text, applicability rule, and evidence rule. When more questions come into scope, evaluate all of them per paper.

---

## The Paper's Form

You receive a markdown conversion of the original PDF or HTML. Extraction may introduce spurious whitespace or collapsed code blocks. Read past the noise; what matters is what the author presented.

---

## Process — per question

### Step 1: Apply the applicability rule

Read the rubric's applicability rule for the question. Decide whether the question applies to this paper.

- If the rule is met, the question is **applicable**.
- If the rule is not met, the question is **not applicable**. Return `applicable: false` and move on; do not look for evidence.

### Step 2: Look for evidence

When the question is applicable, read the paper for a passage that satisfies the rubric's evidence rule. Most papers will not answer any given question — absence is the expected default.

- If you find a passage that clearly answers the question: **applicable and answered**. Include the evidence: a location and a verbatim quote.
- If no such passage exists after a thorough read: **applicable but not answered**. Return `answered: false` without evidence.

### Step 3: Self-test before recording an answer

1. **Is the quote contiguous and verbatim?** The quote must be exact characters from the paper.
2. **Is the quote minimal?** Cite the shortest contiguous passage that answers the question. Target a handful of lines; do not include surrounding material that does not bear on the answer.
3. **Would a reasonable reader agree the quote answers the question?** If the answer requires reading context beyond the quote to understand, the quote is insufficient — find a better passage or record not-answered.

---

## Output

Return one result per in-scope question. Three shapes:

```json
{"question": "Q1", "applicable": false}
```

```json
{"question": "Q1", "applicable": true, "answered": false}
```

```json
{
  "question": "Q1",
  "applicable": true,
  "answered": true,
  "evidence": [
    {"location": "§3.2 ...", "quote": "exact text from the paper"}
  ]
}
```

The pipeline wraps your results into the final output.

---

## Rules

### Do not force an answer
Most papers will not answer any given question. A paper that does not answer is not deficient. Do not stretch to find evidence that isn't there.

### Quote exactly
The quote must be literal text from the paper, character for character.

### Keep quotes minimal
A good quote is a few lines — long enough to carry the answer, short enough to read in seconds.

### Applicability before evidence
Never search for evidence when applicability fails. A non-applicable question simply does not apply; there is nothing to find.

---

## What You Do Not Do

- You do not evaluate paper quality or design choices.
- You do not judge whether the paper will pass committee.
- You do not invent answers when the paper does not provide them.
- You do not report negative findings or gaps; the pipeline handles the unanswered and not-applicable cases mechanically.
