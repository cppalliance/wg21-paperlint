# Paperlint Rubric

## Scope

Evaluate WG21 proposal papers — papers that propose a design addition or change to C++. Do not evaluate Technical Specifications, white papers, working drafts, or pure wording clarifications. If the paper is not a proposal paper, return no findings and identify the paper type.

## Structure

Eight questions about a proposal paper's content, organized as three pillars, plus one universal constraint:

- **Example-based:** Q1, Q2, Q3
- **Principle-based:** Q4, Q5, Q6
- **Alternatives-considered:** Q7, Q8
- **Universal:** U

For each question, a paper either meets the requirement or falls short. A finding is raised for each shortfall.

## Co-occurrence rules

Do not raise both findings in any of these pairs:

- Q1 and Q3 — if Q1 is raised, Q3 is subsumed by the missing motivation.
- Q5 and Q6 — if Q5 is raised, Q6 is subsumed by the missing philosophy argument.
- Q7 and Q8 — if Q7 is raised against thin alternatives, do not raise Q8 against the same weakness. Q8 may be raised only for additional thoroughness gaps beyond Q7.

---

## Pillar 1 — Example-based

### Q1. Motivating examples of current problems

**SD-4 requirement.** "Demonstrate motivating examples of how the code we have to write today is problematic and needs improvement."

**Pass criteria.** The paper contains at least one concrete specimen of current-standard C++ that the author characterizes as problematic — verbose, error-prone, unrepresentable, slow, unreadable, or otherwise deficient in a way the proposal addresses.

**Raise when.** The paper proceeds to the proposed solution without first showing the current state, or it describes a problem in prose without showing current code, or the "motivating examples" shown are actually usage examples of the new feature.

**Do not raise when.** The proposal addresses a problem that is inherently non-code (pure wording fix, definitional clarification) — those are not proposal papers under this rubric.

---

### Q2. Usage examples of the proposed feature

**SD-4 requirement.** "Show specific examples of how the proposed feature is intended to be used."

**Pass criteria.** The paper contains at least one concrete specimen of code using the proposed feature as intended, in a realistic context.

**Raise when.** The paper describes the feature only in prose or grammar productions without showing it in use, or shows only syntax illustrations rather than the feature exercised in a realistic scenario.

**Do not raise when.** The proposal introduces no new syntax or semantics the user writes directly.

---

### Q3. Before/after rewrite of the motivating examples

**SD-4 requirement.** "Including how those motivating examples would look if we had the new proposed feature."

**Pass criteria.** The paper rewrites at least one Q1 motivating example in the form it would take using the proposed feature, making the improvement directly visible.

**Raise when.** Q1 and Q2 are both present but not paired — the motivating problem and the feature's use are shown separately, without the connection that demonstrates improvement.

---

## Pillar 2 — Principle-based

### Q4. Articulated design principles

**SD-4 requirement.** "Articulate the design principles for the proposed solution."

**Pass criteria.** The paper states the design principles guiding the proposed solution — what choices were made and why, at the level of principle. Principles may appear in a dedicated section or inline across the paper.

**Raise when.** The solution is presented without principle-level rationale. The paper explains local mechanics but does not state what the solution optimizes for, what invariants it preserves, or what it deliberately rejects.

**Do not raise when.** The principles are genuinely articulated inline rather than collected. Form does not matter; articulation does.

---

### Q5. Fit with language philosophy

**SD-4 requirement.** "Show how the proposed solution fits with the rest of the language's principles and design philosophy (note: explicitly not with the language's quirks)."

**Pass criteria.** The paper argues how the proposed solution aligns with C++'s broader design philosophy — zero-overhead abstraction, expressiveness without cost, trust the programmer, don't pay for what you don't use, compile-time where possible, or other well-established language-wide principles. The argument may be brief but must be explicit.

**Raise when.** The paper states local principles for the feature (Q4) but does not connect them to C++'s broader philosophy. The feature is presented self-contained, without regard to whether it coheres with the language's identity.

**Do not raise when.** The paper argues the fit in any explicit form. Do not evaluate the correctness of the argument — only its presence.

---

### Q6. Citations to philosophy sources

**SD-4 requirement.** "Ideally include citations of principles/philosophy articulated in The Design and Evolution of C++ (D&E)."

**Pass criteria.** The paper cites D&E or another authoritative philosophy source — Stroustrup's design essays, prior WG21 direction papers (P0939), or equivalent — where it makes philosophy claims.

**Raise when.** The paper argues philosophy fit (Q5) without grounding in any authoritative source.

**Do not raise when.** The philosophy claim is background fact requiring no citation ("C++ values zero overhead"), or the paper cites a prior WG21 direction paper as its philosophy reference.

---

## Pillar 3 — Alternatives-considered

### Q7. Design alternatives considered

**SD-4 requirement.** "Show design alternatives considered... along with concrete examples showing why they were not pursued."

**Pass criteria.** The paper names at least one concrete design alternative and gives a concrete reason it was not pursued. Alternatives may be previously-proposed approaches, naive approaches, or adjacent designs.

**Raise when.** The paper presents a single design as if it were the only option with no discussion of alternatives, or mentions alternatives without concrete rejection reasons.

**Do not raise when.** The design space is genuinely narrow and the paper establishes that with a brief argument. A single alternative with a concrete rejection reason satisfies the requirement.

---

### Q8. Evidence of thoroughness

**SD-4 requirement.** "The author should demonstrate that they have considered the problem reasonably thoroughly, and are not just running with the first idea that occurred to them."

**Pass criteria.** The paper shows evidence of considered thought — interactions with related features addressed, edge cases acknowledged, open questions named, scope limits stated, or similar markers.

**Raise when.** The paper reads as a first-draft sketch: no edge cases, no interaction analysis, no acknowledged open questions, no scope discussion.

**Do not raise when.** Q7 passes with multiple alternatives and concrete reasoning (that is itself evidence of thoroughness). Raise Q8 only for thoroughness gaps distinct from Q7.

---

## Universal — Protected-material quotations

### U. Improper quotation of protected materials

**SD-4 requirement.** Papers may not quote from non-public committee materials — subgroup minutes, meeting wikis, non-public reflectors, ISO-copyrighted final text — except for (a) straw-poll questions and numeric results, and (b) attributed positions with the person's prior consent.

**Pass criteria.** The paper contains no quotations from protected sources, or its quotations fit the two exceptions.

**Raise when.** The paper contains a quotation whose source appears to be a non-public committee material and the quotation is not clearly a straw-poll question/result or an attributed personal position.

**Do not raise when.** The quotation is from a public WG21 paper, the C++ standard draft, a public blog post, or another non-protected source. Consent for personal-position quotations is not visible from the paper; when in doubt, do not raise.
