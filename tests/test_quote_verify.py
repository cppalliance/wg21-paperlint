"""Tests for normalized quote offsets and TOC stripping."""

from tomd.api import _strip_toc
from paperlint.models import Evidence, Finding
from paperlint.pipeline import normalized_char_offset_map, step_verify_quotes


def test_normalized_char_offset_map_basic():
    s = "  hello   world\t\n"
    norm, m = normalized_char_offset_map(s)
    assert norm == "hello world"
    assert len(m) == len(norm)
    assert s[m[0] : m[4] + 1] == "hello"
    assert s[m[6] : m[10] + 1] == "world"


def test_step_verify_quotes_norm_path():
    source = "Intro.\n\nThe   quick   brown\nfox jumps."
    quote = "The quick brown\nfox"
    f = Finding(
        number=1,
        title="t",
        category="c",
        defect="d",
        correction="x",
        axiom="a",
        evidence=[Evidence(location="L1", quote=quote)],
    )
    out = step_verify_quotes([f], source)
    assert len(out) == 1
    ev = out[0].evidence[0]
    assert ev.verified
    span = source[ev.extracted_char_start : ev.extracted_char_end]
    assert "quick" in span and "fox" in span


def test_strip_toc_removes_short_block():
    text = "# Table of Contents\n1. One\n2. Two\n\n# Real Section\nBody."
    got = _strip_toc(text)
    assert "Table of Contents" not in got
    assert "Real Section" in got
    assert "Body." in got


def test_strip_toc_skips_huge_span():
    body = "\n".join([f"{i}. entry" for i in range(400)])
    text = f"# Table of Contents\n{body}\n\n# Next\nX"
    got = _strip_toc(text)
    assert "Table of Contents" in got


def test_strip_toc_not_contents_of_phrase():
    text = "# Contents of the module\nDetails here.\n\n# Other\nOK"
    got = _strip_toc(text)
    assert "Contents of the module" in got
