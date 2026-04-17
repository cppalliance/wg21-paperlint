#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Ground-truth corpus test for the known-FP suppression mechanism.

Tests the three shipping signatures (intra-word spacing, TOC location,
bracketed identifier layout wrap) against a hand-built corpus reconstructed
from reviewer-confirmed false positives and real findings in paperlint-eval.

Run directly:  python tests/test_suppress.py

Expected behavior:
- Should-suppress cases are matched by the expected signature
- Real findings are NOT matched (they pass through)
- Known-gap cases (deferred classes) are NOT matched (they still surface)

This is the pre-regen validation step. If this corpus doesn't pass 100%, we
do not proceed to the full mailing regeneration.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a standalone script from the repo root.
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from paperlint.orchestrator import Evidence, Finding, GatedFinding, PaperMeta
from paperlint.suppress import (
    _is_bracketed_identifier_layout_wrap,
    _is_intra_word_spacing,
    _is_toc_location,
    step_suppress_known_fps,
)


# ---------------------------------------------------------------------------
# Test case schema
# ---------------------------------------------------------------------------
#
# Each case is (name, expected_signature, source_file, defect, location, quotes)
# expected_signature is one of:
#   "intra_word_spacing"
#   "toc_location"
#   "bracketed_identifier_layout_wrap"
#   None  (should pass through — not suppressed)
#
# quotes is a list of strings; each becomes an Evidence entry with the given
# location. First quote's location is the "primary" location used by the TOC
# signature.

TEST_CASES: list[tuple[str, str | None, str, str, str, list[str]]] = [
    # ---------------------------------------------------------------------
    # Should-suppress: shipping signature classes
    # ---------------------------------------------------------------------
    (
        "N5035 #2 'T ooling' intra-word spacing (yesterday's phrasing)",
        "intra_word_spacing",
        "n5035.pdf",
        "The name 'Tooling' for SG15 is rendered with a line break or space splitting 'T' from 'ooling', producing 'T ooling'.",
        "Section 2.2, SG15 entry",
        ["SG15 , T ooling: Michael Spencer, Ben Boeckel"],
    ),
    (
        "N5035 #2 'T ooling' intra-word spacing (2026-04-15 regen phrasing)",
        "intra_word_spacing",
        "n5035.pdf",
        "The name 'Tooling' for SG15 has a spurious space between 'T' and 'ooling', reading as 'T ooling', which is a rendering/line-break artifact.",
        "Section 2.2, SG15 entry",
        ["SG15 , T ooling: Michael Spencer, Ben Boeckel"],
    ),
    (
        "P2583R0 #1 TOC dot-leader concatenation",
        "toc_location",
        "p2583r0.pdf",
        "The Table of Contents uses non-sequential, erratic numbering: sections jump from 4 to 4.1/4.2, then to 5, then 8/5.1/5.2, then 6, 7, 12/7.1, 8, 14/8.1, 15/8.2, 16/8.3, 17/8.4, 9, 10 — mixing section numbers with sub-section numbers of different parents.",
        "Table of Contents",
        [
            "4. std::execution ' s Coroutine Bridges 5. 4.1 Coroutine Completing as Sender 6. 4.2 Sender Co-Awaited by Coroutine 5. Why Sender Algorithms Cannot Provide a Handle 8. 5.1 The Composition Layer 9. 5.2",
            "7. The Proposed Fix and Its Limits 12. 7.1 The Cost 8. Failure To Launch 14. 8.1 Two Entry Points 15. 8.2 spawn Does Not Compile 16. 8.3 on Is a Sender Algorithm 17. 8.4 Implementation Experience",
        ],
    ),
    (
        "P3856R5 TOC missing section 3.2",
        "toc_location",
        "p3856r5.pdf",
        "The table of contents lists sections 3.1, 3.1.1, 3.1.2, and then 3.3, with no section 3.2 present.",
        "Table of Contents",
        ["3.1.2 Proof of concept implementation 7. 3.3 Observations from the sample implementation"],
    ),
    (
        "P4026R0 #3 bracketed identifier layout wrap",
        "bracketed_identifier_layout_wrap",
        "p4026r0.pdf",
        "The stable name reference [meta.reflection. member.queries] contains a spurious space before member, making it malformed.",
        "Potential consequences 1: members_of, prose after code block",
        ["Specializations are invisible for members_of [meta.reflection. member.queries]"],
    ),
    # ---------------------------------------------------------------------
    # Real findings in the same topical neighborhoods — MUST NOT be suppressed
    # ---------------------------------------------------------------------
    (
        "P3984R0 #1 [BS24] duplicate (REAL, hardest control)",
        None,
        "p3984r0.pdf",
        "The bibliography key [BS24] is used for two different works: 'A framework for Profiles development. P3274R0' and 'Programming: Principle and Practice using C++. Addison-Wesley. 2024.'",
        "§6 References",
        [
            "[BS24] B. Stroustrup: A framework for Profiles development. P3274R0. 2024-05-5.",
            "[BS24] B. Stroustrup: Programming: Principle and Practice using C++. Addison-Wesley. 2024. ISBN 978-0-13-830868-1.",
        ],
    ),
    (
        "P3181R1 #1 c2/c3 store/load prose mix-up (REAL)",
        None,
        "p3181r1.pdf",
        "The prose says 'the problematic outcome in which the load at c2 sees 1 isn't possible' but c2 is a store (`a.store(0, non-atomic)`), not a load; the load that might see 1 is c3 (`a.load()`).",
        "§ Stronger semantics are probably still fine, code block",
        [
            "c2: a.store(0, non-atomic);  // initialization of new object, kind of c3: a.load();                // Sees 1?",
            "This seems to be a fairly convincing argument that the problematic outcome in which the load at c2 sees 1 isn't possible on common implementations.",
        ],
    ),
    (
        "P4003R0 #1 executor_ref const-correctness (REAL, semantic)",
        None,
        "p4003r0.pdf",
        "The executor_ref class stores the executor as 'void const* ex_' (exposition-only), but provides a non-const target() overload 'template<executor E> E* target() noexcept;' that returns a mutable pointer, which would require casting away const from the stored const pointer — this is a const-correctness contradiction.",
        "§10.4 Class executor_ref [ioawait.execref]",
        [
            "void const* ex_ = nullptr;                  // exposition only",
            "template<executor E>       E* target() noexcept;",
        ],
    ),
    (
        "P3876R1 #1 grammar finding (REAL)",
        None,
        "p3876r1.pdf",
        "The sentence contains a spurious extra word 'code' making it ungrammatical.",
        "§3.3.1 Unicode error handling",
        ["All Unicode encodings are designed so that code only code points in the Basic Latin block can be encoded with code units in the range [0, 0x7f)."],
    ),
    # ---------------------------------------------------------------------
    # Known-gap cases — deferred classes that should pass through the
    # shipping signatures and still surface as findings. If any of these
    # become suppressed by a shipping signature, it means the signature
    # accidentally widened into deferred territory and needs tightening.
    # ---------------------------------------------------------------------
    (
        "P3984R0 #4 [GDR11] multi-line bib wrap (KNOWN GAP: bib wrap)",
        None,
        "p3984r0.pdf",
        "The reference for [GDR11] is split across two list entries, with the first line having no key and the second line carrying the [GDR11] key, making the bibliography malformed.",
        "§6 References",
        [
            "G. Dos Reis and B. Stroustrup: A Principled, Complete, and Efficient Representation of",
            "[GDR11] C++. Journal of Mathematics in Computer Science Volume 5, Issue 3 (2011).",
        ],
    ),
    (
        "P3984R0 #5 'behandled' hyphen wrap (KNOWN GAP: hyphen wrap)",
        None,
        "p3984r0.pdf",
        "The word 'behandled' is a misspelling of 'be-handled', producing the nonsense compound 'to-behandled-later'.",
        "§2.3 Constructors/destructors",
        ["by putting it on a to-behandled-later error list"],
    ),
    (
        "P3181R1 #2 'does not happen is not' color diff (KNOWN GAP: color diff)",
        None,
        "p3181r1.pdf",
        "The proposed modification to [res.on.objects] shows a 'before' version and 'after' version run together without clear diff markers, and the 'after' version contains the fragment 'or the access does not happen is not' which is garbled.",
        "§ Proposed wording, modification to [res.on.objects]",
        ["If an object of a standard library type is accessed, and the beginning of the object's lifetime (6.8.4) does not happen before the access, or the access does not happen is not 'before' the end of the"],
    ),
    (
        "P3874R1 #1 Rust code block collapse (KNOWN GAP: code block)",
        None,
        "p3874r1.pdf",
        "The Rust code sample for the `get` method shows the SAFETY comment inside the if-block but the actual unsafe call appears outside/after the closing brace of the function body due to formatting.",
        "Appendix: Encapsulating Unsafety, first Rust code block",
        [
            "fn get(self 34 , slice: &[T]) -> Option<&T> { if self < slice.len() { // SAFETY: `self` is checked to be in bounds. } else { None } }",
            "unsafe { Some(slice_get_unchecked(slice, self)) }",
        ],
    ),
]


# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

def _build_finding(defect: str, location: str, quotes: list[str]) -> Finding:
    return Finding(
        number=1,
        title="",
        category="",
        defect=defect,
        correction="",
        axiom="",
        evidence=[Evidence(location=location, quote=q) for q in quotes],
    )


def _build_meta(source_file: str) -> PaperMeta:
    return PaperMeta(
        paper="test",
        title="test",
        authors=[],
        target_group="",
        paper_type="",
        abstract="",
        source_file=source_file,
        run_timestamp="",
        model="",
    )


def _try_all_signatures(finding: Finding, meta: PaperMeta) -> str | None:
    """Run each shipping signature in dispatcher order, return first match name."""
    for fn in (
        _is_intra_word_spacing,
        _is_toc_location,
        _is_bracketed_identifier_layout_wrap,
    ):
        m = fn(finding, meta)
        if m is not None:
            return m.signature_name
    return None


def run_corpus() -> int:
    passed = 0
    failed = 0
    print("=" * 72)
    print("Suppression ground-truth corpus")
    print("=" * 72)

    for name, expected_sig, source_file, defect, location, quotes in TEST_CASES:
        finding = _build_finding(defect, location, quotes)
        meta = _build_meta(source_file)
        actual_sig = _try_all_signatures(finding, meta)

        ok = actual_sig == expected_sig
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
        if not ok:
            print(f"         expected: {expected_sig!r}")
            print(f"         actual:   {actual_sig!r}")

        if ok:
            passed += 1
        else:
            failed += 1

    print()
    print(f"Corpus: {passed}/{passed + failed} passed")
    print()

    # Dispatcher-level test
    print("-" * 72)
    print("Dispatcher test (step_suppress_known_fps over mixed gated list)")
    print("-" * 72)
    gated: list[GatedFinding] = []
    expected_kept_count = 0
    for name, expected_sig, source_file, defect, location, quotes in TEST_CASES:
        finding = _build_finding(defect, location, quotes)
        gated.append(GatedFinding(finding=finding, verdict="PASS", reason=""))
        if expected_sig is None:
            expected_kept_count += 1

    # Dispatch uses a single meta — we need per-finding meta since source_file
    # varies. Run the step once per case and aggregate.
    actual_suppressed_count = 0
    actual_kept_count = 0
    for name, expected_sig, source_file, defect, location, quotes in TEST_CASES:
        finding = _build_finding(defect, location, quotes)
        meta = _build_meta(source_file)
        single_gated = [GatedFinding(finding=finding, verdict="PASS", reason="")]
        kept, suppressed = step_suppress_known_fps(single_gated, meta)
        actual_kept_count += len(kept)
        actual_suppressed_count += len(suppressed)

    dispatch_ok = (
        actual_kept_count == expected_kept_count
        and actual_suppressed_count == (len(TEST_CASES) - expected_kept_count)
    )
    dispatch_status = "PASS" if dispatch_ok else "FAIL"
    print(f"  [{dispatch_status}] dispatcher: kept={actual_kept_count}, suppressed={actual_suppressed_count}")
    print(f"         expected: kept={expected_kept_count}, suppressed={len(TEST_CASES) - expected_kept_count}")

    if not dispatch_ok:
        failed += 1
    else:
        passed += 1

    print()
    print("=" * 72)
    if failed == 0:
        print(f"ALL TESTS PASSED ({passed}/{passed})")
        return 0
    else:
        print(f"FAILURES: {failed}/{passed + failed}")
        return 1


if __name__ == "__main__":
    sys.exit(run_corpus())
