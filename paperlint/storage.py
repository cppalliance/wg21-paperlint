#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Storage abstraction for paperlint outputs.

Defines a backend ABC and a default JSON-on-disk implementation. All
on-disk writes performed by the orchestrator and CLI go through a backend
instance so that a future Postgres backend can drop in without touching
call sites.

Layout used by ``JsonBackend(workspace_dir)``::

    <workspace_dir>/
        mailings/<mailing-id>.json
        <PAPER_ID>/
            paper.md
            meta.json
            evaluation.json
            1-findings.json
            2-gate.json
            2c-suppressed.json

JSON is the only backend today; SQLite is intentionally excluded so that
files remain inspectable when iterating on conversion quality.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StorageBackend(ABC):
    """Abstract storage interface used by paperlint orchestration.

    All methods take plain Python data (dicts/strings); the backend owns
    paths, IDs, encoding, and any transactional concerns.
    """

    @abstractmethod
    def write_paper_md(self, paper_id: str, markdown: str) -> Any:
        """Persist the markdown for a paper. Returns a backend handle."""

    @abstractmethod
    def write_meta_json(self, paper_id: str, meta: dict) -> Any:
        """Persist per-paper metadata (mirrors PaperMeta.asdict())."""

    @abstractmethod
    def write_evaluation_json(self, paper_id: str, evaluation: dict) -> Any:
        """Persist the per-paper evaluation deliverable."""

    @abstractmethod
    def write_intermediate(self, paper_id: str, name: str, payload: Any) -> Any:
        """Persist a labeled intermediate artifact (e.g. ``1-findings``)."""

    @abstractmethod
    def upsert_mailing_index(
        self, mailing_id: str, papers: list[dict]
    ) -> list[dict]:
        """Idempotent merge: keep existing entries (with their original
        ``added`` timestamps), append new ones, return the merged list."""


class JsonBackend(StorageBackend):
    """Filesystem-backed JSON storage rooted at ``workspace_dir``."""

    def __init__(self, workspace_dir: Path | str) -> None:
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def _paper_dir(self, paper_id: str) -> Path:
        d = self.workspace_dir / paper_id.upper()
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_paper_md(self, paper_id: str, markdown: str) -> Path:
        path = self._paper_dir(paper_id) / "paper.md"
        path.write_text(markdown, encoding="utf-8")
        return path

    def write_meta_json(self, paper_id: str, meta: dict) -> Path:
        path = self._paper_dir(paper_id) / "meta.json"
        path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return path

    def write_evaluation_json(self, paper_id: str, evaluation: dict) -> Path:
        path = self._paper_dir(paper_id) / "evaluation.json"
        path.write_text(
            json.dumps(evaluation, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def write_intermediate(
        self, paper_id: str, name: str, payload: Any
    ) -> Path:
        path = self._paper_dir(paper_id) / f"{name}.json"
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def upsert_mailing_index(
        self, mailing_id: str, papers: list[dict]
    ) -> list[dict]:
        index_dir = self.workspace_dir / "mailings"
        index_dir.mkdir(parents=True, exist_ok=True)
        index_path = index_dir / f"{mailing_id}.json"

        existing_by_id: dict[str, dict] = {}
        if index_path.exists():
            for entry in json.loads(index_path.read_text(encoding="utf-8")):
                existing_by_id[entry["paper_id"]] = entry

        now = datetime.now(timezone.utc).isoformat()
        merged: list[dict] = []
        new_count = 0
        for p in papers:
            pid = p["paper_id"]
            if pid in existing_by_id:
                merged.append(existing_by_id[pid])
            else:
                p = dict(p)
                p["added"] = now
                merged.append(p)
                new_count += 1
        merged.sort(key=lambda e: e["paper_id"])

        index_path.write_text(
            json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(
            f"Mailing index: {index_path} ({len(merged)} papers, {new_count} new)"
        )
        return merged

    def mailing_index_path(self, mailing_id: str) -> Path:
        """Public accessor used by callers that need the on-disk path."""
        return self.workspace_dir / "mailings" / f"{mailing_id}.json"
