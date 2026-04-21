# Paperlint Rubric

## Scope

Currently one question is in scope: **Q1**. Additional questions will be added one at a time as each is calibrated. A paper's score is the number of applicable questions it answered out of the applicable questions for that paper.

For each in-scope question and each paper, paperlint produces one of three states:

- **Applicable and answered** — the question applies to the paper and the paper answers it; evidence is a quoted passage.
- **Applicable but not answered** — the question applies but the paper does not answer it.
- **Not applicable** — the question does not apply to this paper type or content.

Scoring uses only applicable questions. "Zero applicable" is a valid state — the paper's page lists the non-applicable questions for completeness and that is all.

## Q1

**Question.** Does the paper show code of the feature it is proposing?

**Applicability.** This question applies when the paper proposes a feature — a new syntax, API, semantic behavior, or language capability that a user can write or call. It does not apply to pure wording clarifications, directional papers, informational reports, or administrative notices, which do not introduce a feature to demonstrate.

**Evidence of an answer.** A passage from the paper that contains a code block showing the proposed syntax or API in use. The code must actually exercise the feature the paper is adding; a mere mention of the feature in prose does not count. The gate verifies that the quoted passage is taken verbatim from the paper and that the code shown actually demonstrates the feature under proposal.

**Source.** SD-4, "High-quality proposal papers" section: *"Show specific examples of how the proposed feature is intended to be used."*
