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
``tomd.lib.html.convert_html``, optionally enriches the resulting markdown's
YAML front matter with fields from the scraped mailing metadata
(`_apply_metadata_fallback`), strips residual table-of-contents blocks as a
safety net, and raises ``RuntimeError`` when tomd returns no usable markdown.
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

# Mailing-metadata key -> YAML front-matter key produced by tomd.
# tomd writes `title`, `document`, `date`, `audience`, `reply-to`; paperlint
# adds the rest under their natural names so downstream consumers can read
# them without needing to know which side wrote them.
_FALLBACK_KEY_MAP = {
    "title": "title",
    "paper_id": "document",
    "document_date": "date",
    "subgroup": "audience",
    "authors": "reply-to",
    "paper_type": "paper-type",
}

_FRONT_MATTER_RE = re.compile(
    r"\A---\s*\n(?P<body>.*?)\n---\s*\n?", re.DOTALL
)


def _strip_toc_replace(m: re.Match[str]) -> str:
    span = m.group(0)
    if span.count("\n") > _TOC_MAX_LINES:
        return span
    return "\n"


def _strip_toc(text: str) -> str:
    """Remove Table of Contents sections that produce phantom findings."""
    return _TOC_RE.sub(_strip_toc_replace, text)


def _yaml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _format_yaml_value(key: str, val) -> str:
    if isinstance(val, list):
        items = "\n".join(f'  - "{_yaml_escape(str(v))}"' for v in val)
        return f"{key}:\n{items}"
    s = str(val)
    if any(c in s for c in ':{}[]#&*?|>!%@`"\'\n\\'):
        return f'{key}: "{_yaml_escape(s)}"'
    return f"{key}: {s}"


def _present_keys(front_matter_body: str) -> set[str]:
    """Return the set of top-level keys already present in a YAML body."""
    keys: set[str] = set()
    for line in front_matter_body.splitlines():
        if not line or line.startswith((" ", "\t", "-", "#")):
            continue
        head, sep, _ = line.partition(":")
        if sep:
            keys.add(head.strip())
    return keys


def _apply_metadata_fallback(md: str, mailing_meta: dict | None) -> str:
    """Inject any missing YAML front-matter fields from ``mailing_meta``.

    If the markdown has no front matter, a fresh block is prepended. If a
    block exists, only fields that are absent from it are added; fields
    already produced by tomd from the source paper win, satisfying the
    directive's "if missing, copy from scraped mailing metadata" rule.
    """
    if not mailing_meta:
        return md

    match = _FRONT_MATTER_RE.match(md)
    if match:
        body = match.group("body")
        present = _present_keys(body)
        rest = md[match.end():]
    else:
        body = ""
        present = set()
        rest = md

    additions: list[str] = []
    for src_key, yaml_key in _FALLBACK_KEY_MAP.items():
        if yaml_key in present:
            continue
        val = mailing_meta.get(src_key)
        if val in (None, "", []):
            continue
        additions.append(_format_yaml_value(yaml_key, val))

    if not additions and match:
        return md

    new_body_lines = [body.rstrip()] if body.strip() else []
    new_body_lines.extend(additions)
    new_body = "\n".join(line for line in new_body_lines if line)

    if new_body:
        return f"---\n{new_body}\n---\n\n{rest.lstrip()}"
    return md


def _convert_with_tomd(path: Path) -> tuple[str, str | None]:
    """Dispatch to the appropriate tomd converter by file suffix."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return convert_pdf(path)
    if suffix in (".html", ".htm"):
        return convert_html(path)
    return convert_html(path)


def extract_text(path: str, mailing_meta: dict | None = None) -> str:
    """Convert a paper to clean markdown via tomd.

    ``mailing_meta`` (optional): the scraped open-std.org mailing index entry
    for this paper. When provided, fills in YAML front-matter fields that
    tomd could not extract from the source.

    Raises ``RuntimeError`` when tomd produces no usable markdown so the
    orchestrator's failure path records a ``pipeline_status = "failed"``.
    """
    p = Path(path)
    md, prompts = _convert_with_tomd(p)

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

    md = _apply_metadata_fallback(md, mailing_meta)
    return _strip_toc(md)
