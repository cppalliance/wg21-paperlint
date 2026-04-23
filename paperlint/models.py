#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Core data models for paperlint.

The discovery/gate side (``Evidence``, ``Finding``, ``GatedFinding``, ``PaperMeta``)
and the deliverable side (``Evaluation`` with ``OutputFinding`` / ``Reference``,
``MailingIndex`` with ``RoomEntry`` / ``IndexPaperEntry`` / ``FailureEntry``)
together describe every JSON contract in ``paperlint/docs/design.md``. Use
:func:`to_dict` when serializing so unset optional fields are omitted rather
than rendered as ``null``, preserving the existing on-the-wire behavior.
"""

from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = "1"


@dataclass
class Evidence:
    location: str
    quote: str
    verified: bool = False
    extracted_char_start: int | None = None
    extracted_char_end: int | None = None


@dataclass
class Finding:
    number: int
    title: str
    category: str
    defect: str
    correction: str
    axiom: str
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class GatedFinding:
    finding: Finding
    verdict: str  # PASS | REJECT | REFER
    reason: str


@dataclass
class PaperMeta:
    paper: str
    title: str
    authors: list[str]
    target_group: str
    paper_type: str
    source_file: str
    run_timestamp: str
    model: str

    @classmethod
    def from_dict(cls, raw: dict) -> "PaperMeta":
        return cls(
            paper=raw["paper"],
            title=raw["title"],
            authors=list(raw["authors"]),
            target_group=raw["target_group"],
            paper_type=raw["paper_type"],
            source_file=raw["source_file"],
            run_timestamp=raw["run_timestamp"],
            model=raw["model"],
        )


@dataclass
class Paper:
    """Canonical in-memory representation of a WG21 paper (design.md §4).

    Declared here to match the spec's signature. Populating all fields
    requires plumbing that does not exist yet: ``mailing_date`` and
    ``publication_date`` are not scraped or extracted today, and
    ``meta_source`` is not tracked in :mod:`paperlint.extract`. Wiring
    :class:`Paper` through ``mailing.py`` / ``extract.py`` /
    ``orchestrator.py`` and migrating :class:`PaperMeta` consumers is
    follow-up work; :class:`PaperMeta` remains the write-side model for
    ``meta.json`` so the on-disk wire format is unchanged by this
    declaration.

    Field semantics (from design.md §4):

    * ``audience`` — short names with no hyphens (``["LEWG", "SG14"]``).
      Section 5 notes "the tag normalization formula is Will's to define";
      no normalizer is provided here.
    * ``intent`` — ``"ask" | "info"``. The mapping from the open-std
      ``paper_type`` values (``proposal`` / ``informational`` /
      ``white-paper`` / ``standing-document``) is not specified in §4 and
      is left to the caller.
    * ``meta_source`` — ``"mailing"`` / ``"tomd"`` / ``"merged"`` provenance
      tag set by whichever component last resolved the metadata.
    """
    document_id: str
    mailing_id: str
    title: str
    authors: list[str]
    mailing_date: str
    publication_date: str
    audience: list[str]
    intent: str
    url: str
    markdown: str
    meta_source: str


@dataclass
class Reference:
    """One reference entry in ``evaluation.references[]``.

    ``extracted_char_*`` are absent when quote verification fell back to
    whitespace-normalized matching without a recoverable offset, so they are
    optional rather than required.
    """
    number: int
    location: str
    quote: str
    verified: bool
    extracted_char_start: int | None = None
    extracted_char_end: int | None = None


@dataclass
class OutputFinding:
    """One finding in ``evaluation.findings[]`` — the deliverable shape.

    Distinct from :class:`Finding` (the discovery shape): the deliverable
    drops ``axiom`` / ``title`` / ``evidence`` and carries integer refs into
    the sibling ``references[]`` list.
    """
    location: str
    description: str
    category: str
    correction: str
    references: list[int] = field(default_factory=list)


@dataclass
class Evaluation:
    """Top-level shape of ``evaluation.json``.

    ``pipeline_status`` is ``complete`` on the happy path, ``failed`` for the
    pre-analysis skeleton, or ``partial`` when analysis raises after metadata
    is available. The four ``failure_*`` fields are populated only on the
    ``partial`` path; :func:`to_dict` omits them when ``None`` so the wire
    format matches the pre-refactor dict construction.
    """
    schema_version: str
    paperlint_sha: str
    prompt_hash: str
    source_url: str
    pipeline_status: str
    paper: str
    title: str
    authors: list[str]
    audience: str
    paper_type: str
    generated: str
    model: str
    findings_discovered: int
    findings_passed: int
    findings_rejected: int
    summary: str
    findings: list[OutputFinding] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    failure_stage: str | None = None
    failure_type: str | None = None
    failure_message: str | None = None
    failure_traceback: str | None = None


@dataclass
class RoomEntry:
    papers: list[str] = field(default_factory=list)
    total_findings: int = 0


@dataclass
class IndexPaperEntry:
    paper: str
    title: str
    audience: str
    findings_passed: int
    findings_discovered: int


@dataclass
class FailureEntry:
    """One entry in ``index.failed_papers[]``.

    ``paper`` is always set; every other field is populated conditionally
    (e.g. ``error`` for pre-analysis exceptions, the ``failure_*`` trio for
    ``partial`` pipeline status). :func:`to_dict` drops unset fields.
    """
    paper: str
    error: str | None = None
    pipeline_status: str | None = None
    summary: str | None = None
    failure_stage: str | None = None
    failure_type: str | None = None
    failure_message: str | None = None
    failure_traceback: str | None = None


@dataclass
class MailingIndex:
    schema_version: str
    paperlint_sha: str
    prompt_hash: str
    mailing_id: str
    generated: str
    total_papers: int
    succeeded: int
    failed: int
    partial: int
    rooms: dict[str, RoomEntry] = field(default_factory=dict)
    papers: list[IndexPaperEntry] = field(default_factory=list)
    failed_papers: list[FailureEntry] | None = None


def _strip_none(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_none(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_none(v) for v in obj]
    return obj


def to_dict(obj: Any, *, omit_none: bool = True) -> Any:
    """Serialize a dataclass (or container of dataclasses) to plain dicts.

    Thin wrapper over :func:`dataclasses.asdict` that filters ``None`` values
    when ``omit_none=True`` (the default). This matches the existing on-the-wire
    convention where optional failure fields are absent rather than ``null``.
    """
    raw = asdict(obj)
    return _strip_none(raw) if omit_none else raw
