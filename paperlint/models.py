#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Core data models for paperlint."""

from dataclasses import asdict, dataclass, field

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
class Paper:
    """Website-facing paper record; mailing index is authoritative for metadata."""

    document_id: str
    mailing_id: str
    title: str
    authors: list[str]
    date: str
    audience: list[str]
    intent: str
    url: str
    markdown: str
    meta_source: str  # "mailing" | "tomd" | "merged"

    def as_meta_json_dict(self) -> dict:
        """Fields persisted to ``meta.json`` (``markdown`` lives only in ``paper.md``)."""
        d = asdict(self)
        del d["markdown"]
        return d


@dataclass
class RunContext:
    """Run-time-only fields for the LLM pipeline (not written to ``meta.json``)."""

    source_file: str
    run_timestamp: str
    model: str
