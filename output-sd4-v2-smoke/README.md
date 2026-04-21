# SD-4 rubric — first smoke review

Five papers from the 2026-02 mailing, run through paperlint v2 on branch `feature/sd4-rubric-v2`. Model: `anthropic/claude-opus-4.6`.

## The rubric — nine questions

Full pass criteria in [`paperlint/rubric.md`](../paperlint/rubric.md).

**Example-based** — Q1 motivating examples · Q2 usage examples · Q3 before/after rewrite

**Principle-based** — Q4 articulated principles · Q5 fit with language philosophy · Q6 citations

**Alternatives-considered** — Q7 design alternatives · Q8 evidence of thoroughness

**Universal** — U improper quotation of protected materials

## The papers

- [P3642R4 — Carry-less product: std::clmul](P3642R4/review.md) · 1 finding
- [P2929R2 — Proposal to add simd_invoke to std::simd](P2929R2/review.md) · 1 finding + 1 REFER
- [N5035 — 2026-03 WG21 admin telecon](N5035/review.md) · out of scope
- [P3874R1 — Should C++ be a memory-safe language?](P3874R1/review.md) · out of scope
- [P4026R0 — Global lookup for begin and end for expansion statements](P4026R0/review.md) · out of scope, possibly miscategorized

## Three questions for your read

1. **Q5 fires on both proposals.** Real pattern that most proposals skip explicit philosophy-fit arguments, or is the bar set too low? Q5 findings are pure absence by definition — no quote to show, only the assertion.

2. **P4026R0 classification.** Title reads like a design change. Metadata said wording. Did we miss a proposal?

3. **P2929R2 Q7 REFER.** Gate declined — a named alternative exists with a rejection reason, but the design space may not be "genuinely narrow" enough. Judgment call we want your read on.
