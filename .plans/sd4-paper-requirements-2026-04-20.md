# SD-4 Paper Requirements — Extraction

Source: [SD-4: WG21 Practices and Procedures](https://isocpp.org/std/standing-documents/sd-4-wg21-practices-and-procedures), dated 2024-12-30.

Extraction date: 2026-04-20.

## What this is

A first-pass extraction of paper requirements from SD-4, organized for downstream work toward a new paperlint rubric. Two principles governed the cull:

1. **Intrinsic to the paper.** We only keep requirements verifiable by reading the paper itself. Requirements about submission timing, presenter presence at meetings, subgroup procedures, ballot mechanics, and other process choreography are dropped.
2. **Surface external dependencies.** Where SD-4 defers to another document (D&E, the ISO/IEC Directives, "How to submit a proposal," an unnamed wording standard), we name the dependency rather than silently keeping or dropping the requirement. That list is the roadmap for future extraction passes.

This document is internal. It is the raw material for thinking through a replacement for the current archaeological rubric, not a rubric itself.

## A. Intrinsic paper requirements

### A.1 For proposal papers (design addition or change)

From the "High-quality proposal papers" section of SD-4, the three explicit criteria — quoted verbatim where the wording matters:

1. **Motivating examples of current problems.** "Demonstrate motivating examples of how the code we have to write today is problematic and needs improvement."

2. **Usage examples of the proposed feature.** "Show specific examples of how the proposed feature is intended to be used."

3. **Before/after comparison.** "Including how those motivating examples would look if we had the new proposed feature."

4. **Articulated design principles.** "Articulate the design principles for the proposed solution."

5. **Fit with language philosophy.** "Show how the proposed solution fits with the rest of the language's principles and design philosophy (note: explicitly not with the language's quirks)." Partially intrinsic — we can verify that fit is *argued*; we cannot verify that the argument is *correct* without the philosophy corpus (see B.1).

6. **Citations of philosophy sources.** "Ideally include citations of principles/philosophy articulated in The Design and Evolution of C++ (D&E)." SD-4 softens this with "ideally" — a strong recommendation rather than a must.

7. **Design alternatives considered.** "Show design alternatives considered... along with concrete examples showing why they were not pursued."

8. **Evidence of thorough consideration.** "The author should demonstrate that they have considered the problem reasonably thoroughly, and are not just running with the first idea that occurred to them."

SD-4 summarizes the force of these points: "These three points are the main things that make the difference between 'someone's cool idea' (which may be interesting but is procedurally unuseful) and 'a real proposal' (that can be seriously evaluated and progressed)."

### A.2 For TS / White paper documents

A distinct paper class. From the "Listing specific goals" section:

9. **Stated learning goals.** "What are we hoping to learn through this TS or white paper?"

10. **Stated exit criteria.** "What are the exit criteria (especially, the list of must-address controversial issues) before we can consider merging this TS or white paper into the IS?"

11. **Firmness scope of initial design.** The document should "outline the extent to which the initial design is considered 'firm' (as opposed to a simple strawman outlining the problem space)."

12. **Questions to users.** The document should state "what questions the committee would like users to help answer."

SD-4 frames the purpose: "A TS or white paper is not an open-ended fishing expedition. It starts with a specific design and aims at answering specific questions."

### A.3 Universal (applies to all papers)

13. **No improper quotation of protected materials.** Papers may not quote from non-public committee materials — subgroup minutes, meeting wikis, non-public reflectors, ISO-copyrighted final text — except for (a) straw-poll questions and numeric results, and (b) words or positions attributed to a specific person with that person's prior consent. Detection of a quotation is intrinsic; verification of consent is not.

## B. Surfaced external dependencies

SD-4 is explicitly a cheat sheet. These are the documents it points at but does not itself define. To evaluate the requirements that depend on them, we would need to ingest them.

1. **The Design and Evolution of C++ (D&E), Stroustrup.** Required to assess requirement A.1/5 ("fits with the language's principles and design philosophy"). Without D&E, we can check that principles are articulated; we cannot check whether the argued alignment holds.

2. **ISO/IEC Directives and JTC 1 Supplement.** Available at https://www.iso.org/directives-and-policies.html. SD-4 positions itself as a summary "in addition to" these. They are the superset — likely source for wording quality, structural, and intellectual-property requirements not repeated in SD-4.

3. **"How to submit a proposal."** At https://isocpp.org/std/submit-a-proposal. SD-4 defers to this page for "whether an implementation is required" and "what ISO intellectual property rules to keep in mind." Both are probable paper requirements.

4. **Standardese / wording quality guide.** SD-4 names "higher quality wording requirements" for TS/white papers and "high-quality standardese wording" for proposals forwarded to CWG/LWG, but does not define the standard. The location of this standard (whether it is in the ISO Directives, a separate WG21 editorial guide, or tacit practice) needs finding.

## C. What we dropped as non-intrinsic

For each, the rationale:

- **On-time papers, late papers.** Timing of submission relative to the pre-meeting mailing deadline. Nothing in the paper itself reveals whether it was on time; paper-date metadata is a proxy at best.
- **Prepared presenters.** Meeting-time requirement that the paper does not carry.
- **Delay vs. bird in the hand, 1-2 year TS lag.** Procedural strategy for subgroup chairs managing the pipeline of competing proposals.
- **Subgroup polls, consensus, plenary mechanics.** Meeting-time procedures.
- **Ballot structure, inappropriate ballot comments, escalation, technical-concern reporting.** Process around papers, not properties of papers.
- **Code of Conduct, ethics slides.** Conduct requirements for participants.
- **Working-draft adoption, editor's reports, draft balloting.** Post-consensus editorial operations.
- **Direction group, study groups, subgroup responsibility, work prioritization.** Organizational structure.
- **"If a proposal doesn't have a paper, it doesn't exist."** A gate that defines our scope of evaluation rather than a property we score — we only evaluate things that are papers.
- **Protected materials publication rules (beyond quotation detection).** Rules about what the committee publishes and how, not what a paper contains.

---

Document status: draft extraction. Basis for discussion toward a new rubric; not for public circulation.
