"""Dispatch PDF/HTML paths to the appropriate converter (library API)."""

from __future__ import annotations

from pathlib import Path

HTML_EXTENSIONS = frozenset({".html", ".htm"})
PDF_EXTENSIONS = frozenset({".pdf"})


class UnsupportedFormatError(ValueError):
    """Raised when the path suffix is not a supported PDF or HTML type."""


def convert_file(
    input_path: Path | str,
    mailing_meta: dict | None = None,
) -> tuple[str, str | None, dict[str, str]]:
    """Convert a single PDF or HTML file to Markdown.

    Returns ``(md_text, prompts_text, provenance)`` like ``convert_pdf`` /
    ``convert_html``. Raises :class:`UnsupportedFormatError` if the suffix
    is not supported.
    """
    path = Path(input_path)
    ext = path.suffix.lower()
    if ext in HTML_EXTENSIONS:
        from .html import convert_html

        return convert_html(path, mailing_meta=mailing_meta)
    if ext in PDF_EXTENSIONS:
        from .pdf import convert_pdf

        return convert_pdf(path, mailing_meta=mailing_meta)
    raise UnsupportedFormatError(f"{path}: unsupported format (expected PDF or HTML)")
