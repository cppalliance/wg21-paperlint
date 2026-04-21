# WG21 Red Team Evaluation Rubric

_Empirically grounded rubric for objective defect detection in WG21 papers._
_Built bottom-up from ~123 findings across 12 papers. Every category has
at least one real specimen._

---

## How to use this rubric

**For the evaluator (human or AI):** Read the paper. For each failure
mode below, check whether the paper exhibits it. If you find a defect,
record it as a **finding** (see Finding Format below). If the paper has
no objective defects, say so.

**For the gate function:** A finding is valid if and only if:
1. It matches a named failure mode in this rubric
2. It quotes exact text from the paper with a location
3. It states a specific, actionable correction
4. Its evidence is grounded in an axiom (see Axiom Set)

A finding that fails any gate criterion is discarded. False negatives
are acceptable. False positives are not.

### Axiom set

These are the only sources of ground truth:

| Axiom | What it grounds |
|-------|----------------|
| **The C++ standard** (current working draft) | Syntax rules, standard library API, semantic requirements |
| **The paper's own text** | Internal consistency — the paper must agree with itself |
| **Referenced documents** | Papers, specs, or standards the paper explicitly cites |
| **Rules of logic** | A claim without evidence is unsupported; a self-contradiction is wrong |

If a finding cannot be traced to one of these axioms, it is out of scope.

### Finding format

```
Finding #N: [short title]
Category: [rubric ID, e.g. 1.2]
Location: [section, page, or stable name]
Quoted text: "[exact text from the paper]"
Defect: [what is wrong — one sentence]
Correction: [what it should say — one sentence]
Axiom: [which axiom grounds this — paper's own text / C++ standard / etc.]
```

---

## Axis 1: C++ Code Samples

### 1.1 Syntax error in code sample

Code that would not compile due to mechanical syntax violations.

**Check:** Parse every code sample. Does it have valid C++ syntax?

**Look for:**
- Missing semicolons after class/struct/union/enum definitions
- Missing or extra colons in scope resolution (`ex:` instead of `ex::`, or `name::<T>` instead of `name<T>`)
- Orphaned lambdas or stray expressions outside any call
- Mismatched braces, parentheses, or angle brackets
- Missing template keyword in dependent contexts

**Example:** `ex:set_stopped_t()` — single colon instead of `ex::set_stopped_t()`.

**Tier:** Observed (5 specimens across 4 papers)

---

### 1.2 Undefined or undeclared identifier in code

Code references a name (variable, function, type, concept) never
declared in scope — not in the paper, not in the standard, not in
any included header.

**Check:** For every name in a code sample, is it declared or imported?

**Look for:**
- Names that are close but not identical to a declared entity (e.g., `is_enumeration_type` where `is_enum_type` is declared)
- Names from a prior revision that were renamed (e.g., `counting_scope_token` renamed to `scope_token`)
- Nonexistent C++ types (e.g., `char_t` — not a standard type)
- Missing `std::` or other namespace qualifiers with no `using` directive

**Example:** `is_enumeration_type(type)` — declared name is `is_enum_type`.

**Tier:** Observed (6 specimens across 4 papers)

---

### 1.3 Inconsistent identifiers across code samples

The same entity is spelled differently in different code blocks, or
within the same block.

**Check:** Does every reference to the same entity use the same spelling
and qualification?

**Look for:**
- Mixed namespace qualification in the same block (`std::isq::height` and bare `isq::height` with no using directive)
- Parameter name mismatches between synopsis and definition (`value` vs `fn`)
- Exposition-only name vs concrete name (`name-type` vs `name_type`)
- Case mismatches on template parameters
- Swapped compound names (`BufferStorage` vs `StorageBuffer`)

**Example:** Same code block uses both `std::isq::altitude` and bare `isq::altitude` with no `using` directive.

**Tier:** Observed (9 specimens across 5 papers)

---

### 1.4 Signature mismatch between synopsis and definition

A class/function synopsis declares one signature; the out-of-line
definition, detailed specification, or informal overview declares
a different one.

**Check:** Compare every declaration point against every other. Do
template parameters, constraints, noexcept, return types, parameter
types, parameter names, and default arguments match?

**Look for:**
- Different default template arguments (`allocator<byte>` vs `allocator<void>`)
- Different constraints (unconstrained vs concept-constrained)
- Different exception specifications (noexcept present vs absent)
- Missing parameters (informal synopsis shows 1 param, formal has 2)
- Missing default argument values (examples call with fewer args than declaration requires)
- Functions present in formal synopsis but absent from informal overview

**Example:** `members_of(info r)` in overview vs `members_of(info r, access_context ctx)` in formal synopsis.

**Tier:** Observed (8 specimens across 4 papers)

---

### 1.5 Missing constexpr/consteval specifier

A declaration omits constexpr/consteval when peer declarations all
have it, or uses constexpr where the paper's own design calls for
consteval (or vice versa).

**Check:** Is the specifier consistent with peer declarations and
with the paper's stated design intent?

**Example:** Poll section says consteval; synopsis says constexpr.

**Tier:** Observed (3 specimens across 2 papers)

---

### 1.6 Corrupted text in code

Characters that are clearly editing artifacts — not typos in the
usual sense, but mechanical corruption.

**Check:** Does the code contain non-ASCII artifacts, digit-for-letter
substitutions, or names that differ from all other occurrences by
a single spurious character?

**Look for:**
- Digit-for-letter substitutions (`2ill` for `will`)
- Extra characters creating a nonexistent name (`impls-fors` for `impls-for`)
- Encoding garbage (U+FFFD, mojibake)

**Example:** `2ill not be a valid non-type` — digit `2` replacing `w`.

**Tier:** Observed (2 specimens across 2 papers)

---

### 1.7 Code sample doesn't do what the paper claims

The code is syntactically valid and may even compile, but its
behavior contradicts what the paper's prose says about it.

**Check:** For every code sample, read the surrounding prose claims.
Does the code actually exhibit the behavior the paper describes?

**Look for:**
- **Wrong output:** Paper says "prints 42" but the code would print something else
- **Wrong compile-time behavior:** Paper says "fails to compile" but the code is well-formed (or vice versa)
- **Wrong constraint semantics:** Paper says "this concept constrains to X" but the concept accepts types it shouldn't (or rejects types it should accept)
- **Wrong complexity/performance:** Paper claims O(1) but the code is visibly O(n)
- **Wrong safety property:** Paper says "thread-safe" but the code has a data race; paper says "exception-safe" but the code leaks on throw
- **Wrong algorithmic behavior:** Paper says "sorts stably" but the code doesn't preserve order; paper says "finds the minimum" but the code finds the maximum
- **Wrong lifetime semantics:** Paper says "extends lifetime" but the code produces a dangling reference
- **Wrong overload/ADL behavior:** Paper says "calls overload #2" but resolution would pick #1
- **Demonstrated pattern doesn't match claim:** Paper says "demonstrates CRTP" but the code uses simple inheritance

**Axiom:** The paper's own text. The claim is in the prose; the
evidence is in the code. If they disagree, that's an objective
defect regardless of whether the code or the prose is "right."

**Note:** This category is broader than the others in Axis 1.
Sub-patterns will be refined as specimens are observed. The key
detection question is always: *does the prose make a specific,
verifiable claim about the code's behavior, and does the code
actually exhibit that behavior?*

**Tier:** Anticipated — logically certain to occur (proposals
routinely describe what their examples do) but not yet cataloged
with specific specimens. Promoting to Observed is a Phase S/E goal.

---

### 1.8 Code sample violates C++ standard requirements

The code compiles (or appears to) but violates a requirement in
the C++ standard — undefined behavior, ill-formed NDR, violated
precondition, or misuse of a standard library component.

**Check:** For every code sample, does it comply with the standard
requirements for the constructs it uses?

**Look for:**
- **Undefined behavior:** Dangling references, use-after-move, signed integer overflow, null pointer dereference, data races
- **Library precondition violations:** Invalid iterator operations, out-of-range access, wrong allocator requirements
- **Template instantiation failures:** Code claims to instantiate but substitution would fail
- **Concept satisfaction errors:** Types claimed to satisfy a concept that they don't
- **ODR violations:** Multiple definitions with different meanings
- **Lifetime errors:** Temporaries bound incorrectly, returning references to locals

**Axiom:** The C++ standard (specific cited section).

**Note:** This category will be expanded significantly in Phase S
(Standards-Based Code Critique Mining), which will mine WG21
reflector discussions and community critique patterns to enumerate
the specific sub-modes that reviewers actually flag in practice.
The sub-patterns listed above are a starting scaffold.

**Tier:** Anticipated — our A4 from the original taxonomy. Specific
specimens and sub-categories are a Phase S deliverable.

---

## Axis 2: Standardese / Wording

### 2.1 Misspelled word in prose or wording

Simple typo in natural language text. Applies to both normative
wording and non-normative discussion.

**Check:** Spell-check all text, especially proposed normative wording.

**Look for:** Standard misspellings. Prioritize normative wording sections —
a typo in normative text becomes a defect in the C++ standard itself.

**Example:** `instantation` for `instantiation` in proposed `[lex.phases]` wording.

**Tier:** Observed (18+ specimens across every paper analyzed)

---

### 2.2 Misspelled identifier or type name in prose

A C++ identifier, type name, or function name is misspelled in
running text (not in a code block).

**Check:** Does every C++ name in prose match its declaration?

**Look for:**
- Extra/missing/swapped letters (`set_stoppped`, `execption_ptr`, `polymorphic_alloctor`)
- Truncated names (`optiona`)
- Semantic near-misses (`reminder` for `remainder`)

**Example:** `execution::as_waitable` — correct name is `as_awaitable`.

**Tier:** Observed (9 specimens across 5 papers)

---

### 2.3 Grammar error in prose

Mechanical grammar errors in natural language.

**Check:** Basic grammatical analysis of every sentence.

**Look for:**
- Subject-verb disagreement
- Missing words or prepositions (`contextually converted bool` → `to bool`)
- Doubled words or phrases (`a a polymorphic`, `should be should be`)
- Run-on sentences (missing terminal punctuation)
- Singular/plural mismatches

**Example:** `E shall be a a polymorphic class type` — doubled article.

**Tier:** Observed (14 specimens across 7 papers)

---

### 2.4 Broken cross-reference or stable name

Reference to a standard stable name that is malformed, nonexistent,
or points to the wrong section.

**Check:** Is every `[stable.name]` well-formed, valid, and pointing
to the right section?

**Look for:**
- Double brackets `[[section.name]]` (attribute syntax, not cross-ref)
- Extra/missing brackets
- Typos in stable name (`[exex.as.awaitable]`)
- Correct stable name but wrong section (`[namespace.alias]` for namespaces)
- Dead links using stable names as href targets

**Example:** `[namespace.alias]` used where `[namespace.def]` is intended.

**Tier:** Observed (7 specimens across 5 papers)

---

### 2.5 Prose contradicts own code or synopsis

Design discussion describes one API; proposed wording or synopsis
says something different.

**Check:** Does every prose description match the corresponding
code or synopsis?

**Look for:**
- Prose says N overloads, synopsis has a different number
- Prose describes one parameter type, synopsis has another
- Design section says consteval, wording says constexpr
- Undefined metavariables in normative wording

**Example:** Prose describes two distinct `substr` overloads; synopsis
has only one function with default arguments.

**Tier:** Observed (6 specimens across 5 papers)

---

### 2.6 Incorrect factual claim (internal)

The paper states something about itself or about C++ history that
is verifiably wrong.

**Check:** Verify every factual claim within the paper.

**Look for:**
- Wrong C++ version for a feature (`C++14` for string_view — it's C++17)
- Wrong year for a meeting
- Inverted semantic predicates (`must not terminate` vs `must not return`)
- Incorrect characterization of C++ semantics

**Example:** `C++14 added std::string_view` — string_view is C++17.

**Tier:** Observed (4 specimens across 3 papers)

---

### 2.7 Broken diff-splicing

Proposed wording diffs that, when applied (delete struck-through,
insert underlined), produce malformed text.

**Check:** Mentally apply every diff. Does the resulting text read
as coherent English/standardese? Does the "before" text match the
actual baseline?

**Look for:**
- Orphaned conjunctions or connectives after deletion
- List items reduced to bare connectives
- Ambiguous antecedents after list expansion (`that statement` now ambiguous)
- Misquoted "before" text (dropped words, misspellings) that won't match when applied
- Deletion boundaries that split a grammatical unit

**Example:** Diff deletes `or` and expands a two-item list to four items,
but `that` still reads as singular — ambiguous antecedent.

**Tier:** Observed (3 specimens across 3 papers)

---

### 2.8 Mechanically broken standardese clause

Normative wording that violates deterministic rules of C++ standardese —
where only one correct form exists, not where editorial style varies.

**Check:** Does each clause use the correct C++ form for what it
expresses? Are numbering sequences valid?

**Look for:**
- `is_void<T>` used as boolean instead of `is_void_v<T>` (type vs value trait form)
- Misordered or duplicated paragraph/sub-item numbering
- Malformed EBNF/BNF productions (premature terminators, missing symbols)
- Stray keywords inside clause bodies (`returns` instead of `return` in Effects)

**Not in scope:** Which clause heading a requirement belongs under
(Effects vs Returns vs Remarks) is editorial discretion, not a
mechanical error. Do not flag wording placement preferences.

**Example:** `is_void<T> is true` — `is_void<T>` is a type, not a value.
Should be `is_void_v<T>`.

**Tier:** Observed (5 specimens across 3 papers)

---

### 2.9 Wrong API or function name in wording

The paper names a standard library entity that either doesn't exist
or is the wrong entity for the context.

**Check:** Does every named standard entity exist and have the
semantics the paper assumes?

**Look for:**
- Deprecated/removed name used instead of current (`uncaught_exception` for `unhandled_exception`)
- Wrong completion channel (`set_value` where `set_error` required)
- Names from other languages or frameworks

**Example:** `void uncaught_exception();` in coroutine promise —
standard requires `unhandled_exception()`.

**Tier:** Observed (2 specimens in 1 paper)

---

### 2.10 Inconsistent grammar production names

The paper introduces or references a grammar production under one
name in one section and a different name in another.

**Check:** Are all grammar production names and exposition-only names
consistent throughout?

**Look for:**
- Different names in informal overview vs formal wording (`let-binding` vs `let-pattern`)
- Typos in production names that create a nonexistent production (`conteval-block-declaration`, `posfix-expression`)
- Enum enumerator names that don't match prose references (`close` in enum, `closed` in prose)
- Different suffixes (`escape-statement` vs `escaping-statement`)

**Example:** Grammar defines `escape-statement`; normative prose
references `escaping-statement` which does not exist in the grammar.

**Tier:** Observed (7 specimens across 4 papers)

---

### 2.11 Self-referential or circular definition

A concept, constraint, or definition references itself rather than
its intended base.

**Check:** Does every definition reference a distinct entity?

**Look for:**
- Concept that refines itself instead of its base concept
- Recursive constraint that doesn't terminate
- Definition whose defining term appears in the definiens

**Example:** `concept async-concurrent-queue = async-concurrent-queue<Q> && ...`
— refines itself instead of `basic-concurrent-queue<Q>`.

**Tier:** Observed (1 specimen — genuinely rare)

---

## Axis 3: External Consistency

_These checks require ground truth from outside the paper._

### 3.1 Wording diff base text doesn't match working draft

The "before" text in a proposed wording diff doesn't match the cited
standard section.

**Check:** Compare every diff's struck-through text against the cited
working draft. Does it match exactly?

**Look for:**
- Missing bullets/paragraphs not shown as deleted
- Text that doesn't exist in any published draft
- Paper diffing against an unpublished intermediate draft
- Subtle word differences (missing articles, different ordering)

**Example:** Paper's diff starts at bullet (2.1), but the actual standard
has 8 bullets — the diff silently drops the first two without
striking them through.

**Axiom:** The C++ standard (specific cited draft).

**Tier:** Observed (3 specimens in 1 paper)
**Note:** Highest-value category. If the diff doesn't apply, the editor
cannot merge the paper.

---

### 3.2 Superseded baseline

Another paper (already adopted) has removed or replaced the working
draft text that this paper claims to modify.

**Check:** Is the text being modified still present in the current
working draft?

**Look for:**
- Paper says "relative to N####" but that draft has since been superseded
- Section the paper modifies was rewritten by a different paper
- Features the paper builds on were removed entirely

**Example:** Paper modifies trivial relocation wording from P2786, but
P3920R0 (adopted at Kona) removed that entire wording.

**Axiom:** The C++ standard (current draft).

**Tier:** Observed (1 specimen — genuinely rare but devastating)

---

### 3.3 Reference to nonexistent standard entity

The paper references a function, type, concept, or section that
doesn't exist in the C++ standard or any referenced document.

**Check:** Does every referenced standard entity actually exist?

**Look for:**
- `std::get_current_exception()` (correct: `std::current_exception()`)
- `execution::as_waitable` (correct: `execution::as_awaitable`)
- Stable names that don't correspond to any section

**Axiom:** The C++ standard.

**Tier:** Observed (2 specimens in 1 paper)

---

### 3.4 Semantic violation of standard requirements

The paper's proposed wording or API design violates a requirement
defined in the C++ standard.

**Check:** Does the proposed API satisfy the standard requirements
it claims to meet?

**Look for:**
- Stop token queried from wrong object (sender vs receiver)
- Concept definition that is ill-formed per `[temp.concept]`
- Return type that doesn't satisfy the concept it claims to model
- Preconditions/postconditions that contradict standard invariants

**Axiom:** The C++ standard (cited section).

**Tier:** Observed (3 specimens in 1 paper)
**Note:** High-value, hard to detect. Requires standard knowledge.

---

### 3.5 Incorrect factual claim about external document

The paper makes a verifiably false claim about another paper, a
meeting, or the standard.

**Check:** Verify claims against the referenced documents.

**Look for:**
- Wrong meeting year or location
- Wrong/incomplete author list
- Bibliography URL pointing to a different paper entirely
- Wrong paper number in a citation

**Axiom:** The referenced document.

**Tier:** Observed (4 specimens across 2 papers)

---

## Axis 4: Meta / Document Production

### 4.1 Unresolved placeholder

Content markers that should have been filled in before publication.

**Check:** Search for placeholder patterns.

**Look for:**
- `YYYYMML`, `2025XXL`, `YYYMML` in feature-test macros
- `TBD` for paper numbers
- `TODO` markers
- `???` or `FIXME`

**Example:** `#define __cpp_lib_task YYYMML` — also note wrong digit
count (convention is 7 characters: YYYYMML).

**Tier:** Observed (6 specimens across 5 papers)

---

### 4.2 Metadata error

Paper number, revision, date, or author fields are internally
inconsistent.

**Check:** Cross-check all metadata fields against each other and
against the document filename/URL.

**Look for:**
- Wrong revision number in history preamble ("revises R1" should be "R18")
- Wrong paper number (P0269 for P0260)
- Stale self-reference ("This revision (R4)" in an R7 paper)
- Date inconsistencies

**Example:** `This paper revises P0260R1` — R19 revises R18, not R1.

**Tier:** Observed (5 specimens across 3 papers)

---

### 4.3 Toolchain rendering artifact

The document generation toolchain produced broken output.

**Check:** Look for rendering anomalies.

**Look for:**
- U+FFFD replacement characters (unresolved cross-references)
- Unrendered markup in output (raw markdown bold markers in HTML)
- href/display-text inversion on all links (systematic)
- CSS class typos preventing style application (`drafnote` for `draftnote`)
- Empty/invalid XHTML attributes

**Example:** Every external link in the paper has href and display text
swapped — systematic toolchain bug.

**Tier:** Observed (6 specimens across 5 papers)

---

### 4.4 Bibliography error

Errors in the references/bibliography section.

**Check:** Verify bibliography entries.

**Look for:**
- Duplicate authors in a single entry
- Inconsistent key casing (R vs r in revision suffixes)
- URL pointing to a different paper than labeled
- Missing authors

**Example:** Author list for [P2786R13] includes Pablo Halpern twice
and omits two actual authors.

**Tier:** Observed (4 specimens across 4 papers)

---

### 4.5 Duplicate HTML IDs

Multiple HTML elements share the same `id` attribute.

**Check:** Scan for duplicate id attributes.

**Look for:**
- Auto-generated code block IDs that collide (`id="cb1"` appearing twice)
- Section heading IDs that collide due to repeated headings

**Example:** `id="cb1"` used for both a C++ code block and a C# code
block in different sections.

**Tier:** Observed (2 specimens across 2 papers)

---

### 4.6 Empty or placeholder section

A section exists in the document structure but contains no
substantive content.

**Check:** Does every section have content?

**Look for:**
- Revision history entries with no description
- Content sections containing only "TBD"
- Sections with a heading but no body text

**Example:** Section 11.6 "Vector and tensor quantities" contains only "TBD".

**Tier:** Observed (3 specimens across 2 papers)

---

## Anticipated Failure Modes (Tier 2)

These are logically possible but not yet observed in the corpus.
They should be checked but findings are flagged for extra scrutiny.

| ID | Failure mode | Why it could occur |
|----|-------------|-------------------|
| A1 | Template parameter arity mismatch | Wrong number of template arguments |
| A2 | Feature-test macro value wrong format | Not matching YYYYMML convention |
| A3 | Stable name points to wrong draft edition | Version mismatch between paper and reference |
| ~~A4~~ | ~~Code compiles but has undefined behavior~~ | Promoted to 1.8 |
| A5 | Normative "shall" where "should" intended | Binding vs non-binding language |
| A6 | Wording uses deprecated standard term | e.g., "POD" instead of current terminology |
| A7 | Feature-test macro name collides with existing | Namespace pollution |
| A8 | Paper claims ABI compatibility without evidence | Unsupported assertion |

---

## Out of scope

Anything that requires **judgment rather than citation**:

- Quality or sufficiency of motivation
- Design alternatives not considered
- Ecosystem or adoption concerns
- "This would be better if..."
- Any finding where two experts might reasonably disagree

When in doubt, discard. A false negative (missed real defect) is
acceptable. A false positive (hallucinated or subjective finding)
is not.

---

## Provenance

This rubric was constructed from empirical analysis of 12 WG21
papers spanning library proposals, language features, executors,
reflection, pattern matching, and utility types. Papers ranged from
R0 first drafts to R19 mature revisions.

**Construction methodology:**
1. Wave 1: Open-ended defect harvest across 8 papers (85 findings)
2. Wave 1b: External consistency verification with web search (17 findings)
3. Wave 2: Gap-targeted analysis of 4 additional papers (~38 findings)
4. Taxonomy: Bottom-up clustering into 28 categories across 4 axes
5. Top-down completeness check: 8 anticipated categories added

See `rubric/taxonomy.md` for the full taxonomy with specimen counts
and `rubric/harvest.md` for the raw finding catalog.
