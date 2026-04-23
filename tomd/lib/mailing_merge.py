"""Merge open-std mailing index rows into tomd YAML metadata (mailing wins per key)."""

from __future__ import annotations

import re
from typing import Any

# Canonical YAML front-matter keys and emission order (see paperlint client directive).
FRONT_MATTER_KEYS = (
    "title",
    "document",
    "date",
    "intent",
    "audience",
    "reply-to",
)

_AUDIENCE_CODE_RE = re.compile(
    r"\b(WG21|LEWG|LWG|EWG|CWG|SG\d+)\b",
    re.IGNORECASE,
)


def parse_audience_codes(subgroup: str) -> list[str]:
    """Extract short WG21 subgroup codes from a mailing ``subgroup`` string."""
    if not subgroup or not str(subgroup).strip():
        return ["WG21"]
    s = str(subgroup).strip()
    if re.search(r"(?i)all\s+of\s+wg21", s):
        return ["WG21"]
    out: list[str] = []
    seen: set[str] = set()
    for m in _AUDIENCE_CODE_RE.finditer(s):
        raw = m.group(1)
        if raw.lower().startswith("sg"):
            code = "SG" + raw[2:].upper()
        else:
            code = raw.upper()
        if code not in seen:
            seen.add(code)
            out.append(code)
    return out if out else ["WG21"]


def normalize_intent(raw: str | None) -> str:
    """Map mailing ``paper_type`` / legacy labels to ``info`` or ``ask``."""
    if raw is None or raw == "":
        return "ask"
    s = str(raw).strip().lower()
    if s in ("info", "ask"):
        return s
    if s in ("proposal", "proposed"):
        return "ask"
    if s in (
        "informational",
        "white-paper",
        "white paper",
        "standing-document",
        "standing document",
    ):
        return "info"
    return "ask"


def _empty(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and not val.strip():
        return True
    if isinstance(val, (list, tuple)) and len(val) == 0:
        return True
    return False


def _mailing_values(mailing_meta: dict) -> dict[str, Any]:
    """Map mailing JSON row to canonical YAML-shaped values."""
    title = (mailing_meta.get("title") or "").strip() or None
    pid = (mailing_meta.get("paper_id") or "").strip()
    document = pid.upper() if pid else None
    date = (mailing_meta.get("document_date") or "").strip() or None
    intent = normalize_intent(mailing_meta.get("paper_type"))
    subgroup = mailing_meta.get("subgroup") or ""
    audience = parse_audience_codes(subgroup)
    authors = mailing_meta.get("authors") or []
    if isinstance(authors, str):
        authors = [a.strip() for a in authors.split(",") if a.strip()]
    elif not isinstance(authors, list):
        authors = []
    reply_to = authors if authors else None
    return {
        "title": title,
        "document": document,
        "date": date,
        "intent": intent,
        "audience": audience,
        "reply-to": reply_to,
    }


def merge_yaml_with_mailing(
    source_metadata: dict,
    mailing_meta: dict | None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Merge tomd-extracted metadata with a mailing row; mailing wins per key.

    Returns ``(merged_metadata, provenance)`` where provenance maps each
    emitted YAML key to ``\"mailing\"`` or ``\"tomd\"``.
    """
    provenance: dict[str, str] = {}
    merged: dict[str, Any] = {}

    if not mailing_meta:
        for key in FRONT_MATTER_KEYS:
            val = source_metadata.get(key)
            if val is None and key == "intent":
                val = source_metadata.get("paper-type")
            if _empty(val):
                continue
            merged[key] = val
            provenance[key] = "tomd"
        for key, val in source_metadata.items():
            if key in FRONT_MATTER_KEYS or key == "paper-type":
                continue
            if not _empty(val):
                merged[key] = val
                provenance[key] = "tomd"
        return merged, provenance

    mailing_vals = _mailing_values(mailing_meta)

    for key in FRONT_MATTER_KEYS:
        mv = mailing_vals.get(key)
        if not _empty(mv):
            merged[key] = mv
            provenance[key] = "mailing"
            continue
        sv = source_metadata.get(key)
        if key == "intent" and sv is None:
            sv = source_metadata.get("paper-type")
        if not _empty(sv):
            merged[key] = sv
            provenance[key] = "tomd"

    for key, val in source_metadata.items():
        if key in FRONT_MATTER_KEYS or key == "paper-type":
            continue
        if not _empty(val):
            merged[key] = val
            provenance[key] = "tomd"

    return merged, provenance


def rollup_meta_source(provenance: dict[str, str]) -> str:
    """``mailing`` | ``tomd`` | ``merged`` for keys in ``FRONT_MATTER_KEYS`` only."""
    labels = [provenance.get(k) for k in FRONT_MATTER_KEYS if k in provenance]
    if not labels:
        return "tomd"
    if all(x == "mailing" for x in labels):
        return "mailing"
    if all(x == "tomd" for x in labels):
        return "tomd"
    return "merged"
