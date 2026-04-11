#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Text extraction from WG21 paper HTML and PDF files.

Provides clean text for Sonnet metadata extraction. Discovery gets the raw
source (HTML/PDF bytes) directly via the Citations API — this module is only
used for the metadata step.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser


class _PaperContentExtractor(HTMLParser):
    """Extract readable content from WG21 paper HTML.

    Preserves:
    - All text content
    - Code blocks verbatim (content inside <code>, <pre>)
    - Diff notation as markers: <<+inserted text+>> <<-deleted text->>
    - Section structure via headings

    Strips:
    - All HTML tags (but keeps their text content)
    - Style blocks, script blocks
    - Navigation/metadata chrome
    """

    def __init__(self):
        super().__init__()
        self.output: list[str] = []
        self.skip_stack: list[str] = []
        self.in_code = 0
        self.in_diff_add = 0
        self.in_diff_del = 0
        self.in_style = False
        self.in_script = False
        self.in_head = False
        self.last_was_block = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr_dict = dict(attrs)
        classes = (attr_dict.get("class") or "").split()

        if tag == "head":
            self.in_head = True
            return
        if tag == "body":
            self.in_head = False
        if tag == "style":
            self.in_style = True
            return
        if tag == "script":
            self.in_script = True
            return

        if self.in_head or self.in_style or self.in_script:
            return

        if tag in ("code", "pre"):
            if self.in_code == 0 and tag == "pre":
                self.output.append("\n```\n")
            self.in_code += 1
            return

        if tag == "ins" or "add" in classes:
            self.in_diff_add += 1
            self.output.append("\u00ab+")
            return
        if tag == "del" or "rm" in classes:
            self.in_diff_del += 1
            self.output.append("\u00ab-")
            return

        if tag in ("p", "div", "li", "tr", "blockquote", "section", "article"):
            if not self.last_was_block:
                self.output.append("\n")
                self.last_was_block = True

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            self.output.append(f"\n{'#' * level} ")
            self.last_was_block = True

    def handle_endtag(self, tag: str):
        if tag == "head":
            self.in_head = False
            return
        if tag == "style":
            self.in_style = False
            return
        if tag == "script":
            self.in_script = False
            return

        if self.in_head or self.in_style or self.in_script:
            return

        if tag in ("code", "pre"):
            self.in_code = max(0, self.in_code - 1)
            if self.in_code == 0 and tag == "pre":
                self.output.append("\n```\n")
            return

        if tag == "ins" or (tag == "span" and self.in_diff_add > 0):
            self.in_diff_add = max(0, self.in_diff_add - 1)
            self.output.append("+\u00bb")
            return
        if tag == "del" or (tag == "span" and self.in_diff_del > 0):
            self.in_diff_del = max(0, self.in_diff_del - 1)
            self.output.append("-\u00bb")
            return

        if tag in ("p", "div", "li", "tr", "blockquote", "section", "article"):
            self.output.append("\n")
            self.last_was_block = True

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.output.append("\n")
            self.last_was_block = True

    def handle_data(self, data: str):
        if self.in_head or self.in_style or self.in_script:
            return

        if self.in_code > 0:
            self.output.append(data)
        else:
            text = re.sub(r"[ \t]+", " ", data)
            if text.strip():
                self.last_was_block = False
            self.output.append(text)

    def handle_entityref(self, name: str):
        if self.in_head or self.in_style or self.in_script:
            return
        entity_map = {"lt": "<", "gt": ">", "amp": "&", "quot": '"', "apos": "'"}
        self.output.append(entity_map.get(name, f"&{name};"))

    def handle_charref(self, name: str):
        if self.in_head or self.in_style or self.in_script:
            return
        try:
            if name.startswith("x"):
                self.output.append(chr(int(name[1:], 16)))
            else:
                self.output.append(chr(int(name)))
        except (ValueError, OverflowError):
            self.output.append(f"&#{name};")

    def get_text(self) -> str:
        raw = "".join(self.output)
        cleaned = re.sub(r"\n{3,}", "\n\n", raw)
        cleaned = re.sub(r" +\n", "\n", cleaned)
        cleaned = re.sub(r"\n +", "\n", cleaned)

        parts = cleaned.split("```")
        for i in range(0, len(parts), 2):
            if i < len(parts):
                parts[i] = re.sub(r" {2,}", " ", parts[i])
        cleaned = "```".join(parts)

        return cleaned.strip()


def extract_html(path: str) -> str:
    """Extract clean text from an HTML paper."""
    with open(path) as f:
        html = f.read()
    extractor = _PaperContentExtractor()
    extractor.feed(html)
    return extractor.get_text()


def extract_pdf(path: str) -> str:
    """Extract clean text from a PDF paper using pymupdf."""
    import pymupdf
    doc = pymupdf.open(path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def extract_text(path: str) -> str:
    """Extract clean text from a paper (HTML or PDF).

    Dispatches by file extension. Returns clean text suitable for
    metadata extraction. Discovery gets the raw source instead.
    """
    if path.lower().endswith(".pdf"):
        return extract_pdf(path)
    return extract_html(path)
