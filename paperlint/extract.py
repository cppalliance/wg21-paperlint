#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Paper-to-markdown extraction wrapper around ``tomd``.

`extract_text` is the single entry point used by the pipeline (`step_metadata`
in `paperlint.pipeline`) and by `convert_one_paper` in the orchestrator. It
dispatches by file suffix to ``tomd.lib.pdf.convert_pdf`` or
``tomd.lib.html.convert_html``, passing the scraped mailing row so **tomd**
merges YAML front matter (mailing wins per key; see ``tomd.lib.mailing_merge``).
This module only strips residual table-of-contents blocks and surfaces
per-field provenance from tomd.

Raises ``RuntimeError`` when tomd produces no usable markdown.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from tomd.lib.html import convert_html
from tomd.lib.pdf import convert_pdf

# Strip dot-leader TOC blocks; refuse overly large matches (not a real TOC).
_TOC_MAX_LINES = 300
_TOC_RE = re.compile(
    r"(?m)^(?:#{1,3}\s*)?(?:Table of )?Contents\s*$\r?\n?"
    r"(.*?)"
    r"(?=\r?\n#{1,3}\s|\Z)",
    re.DOTALL | re.IGNORECASE,
)


def _strip_toc_replace(m: re.Match[str]) -> str:
    span = m.group(0)
    if span.count("\n") > _TOC_MAX_LINES:
        return span
    return "\n"


def _strip_toc(text: str) -> str:
    """Remove Table of Contents sections that produce phantom findings."""
    return _TOC_RE.sub(_strip_toc_replace, text)


def _convert_with_tomd(path: Path, mailing_meta: dict | None) -> tuple[str, str | None, dict[str, str]]:
    """Dispatch to the appropriate tomd converter by file suffix."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return convert_pdf(path, mailing_meta=mailing_meta)
    if suffix in (".html", ".htm"):
        return convert_html(path, mailing_meta=mailing_meta)
    return convert_html(path, mailing_meta=mailing_meta)


def extract_text(path: str, mailing_meta: dict | None = None) -> tuple[str, dict[str, str]]:
    """Convert a paper to clean markdown via tomd.

    Returns ``(markdown, provenance)`` where ``provenance`` maps YAML keys to
    ``\"mailing\"`` or ``\"tomd\"`` (see ``tomd.lib.mailing_merge``).

    ``mailing_meta``: one row from ``mailings/<id>.json`` (open-std scrape).

    Raises ``RuntimeError`` when tomd produces no usable markdown so the
    orchestrator's failure path records a ``pipeline_status = \"failed\"``.
    """
    p = Path(path)
    md, prompts, provenance = _convert_with_tomd(p, mailing_meta)

    if prompts:
        print(
            f"paperlint [extract] tomd issues for {p.name}:\n{prompts}",
            file=sys.stderr,
        )

    if not md or not md.strip():
        raise RuntimeError(
            f"tomd produced empty markdown for {p} (slide deck, "
            f"standards draft, or unreadable PDF)."
        )

    return _strip_toc(md), provenance
