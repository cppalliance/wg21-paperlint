#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Paperstore: storage abstraction for paperflow artifacts."""

from __future__ import annotations

import os
from pathlib import Path

from paperstore.backend import StorageBackend
from paperstore.errors import (
    MissingMailingIndexError,
    MissingMetaError,
    MissingPaperError,
    MissingPaperMdError,
    MissingSourceError,
    PaperstoreError,
)
from paperstore.json_backend import JsonBackend

WORKSPACE_ENV_VAR = "PAPERFLOW_WORKSPACE"


def default_workspace_dir() -> Path:
    """Resolve the default workspace path: ``$PAPERFLOW_WORKSPACE`` or ``./data``.

    Empty or unset env var yields ``./data`` (cwd-relative).
    """
    env = os.environ.get(WORKSPACE_ENV_VAR, "").strip()
    return Path(env) if env else Path("./data")


def from_uri(
    uri: str | None = None, *, workspace_dir: Path | str | None = None
) -> StorageBackend:
    """Construct a storage backend from a URI.

    - ``None`` or ``"file://<path>"`` returns a :class:`JsonBackend`.
    - Any other scheme is reserved for future backends (e.g. ``postgres://``).
    """
    if uri is None or uri == "":
        if workspace_dir is None:
            raise ValueError(
                "paperstore.from_uri requires workspace_dir when uri is None or empty "
                f"(got uri={uri!r}, workspace_dir=None)."
            )
        return JsonBackend(workspace_dir)
    if uri.startswith("file://"):
        path = uri[len("file://"):] or workspace_dir
        if path is None:
            raise ValueError(
                f"paperstore.from_uri: file:// URI has no path and no workspace_dir "
                f"fallback (uri={uri!r})."
            )
        return JsonBackend(path)
    raise ValueError(
        f"paperstore.from_uri: unsupported URI scheme (uri={uri!r}); "
        "only None, '', and file:// are recognized."
    )


__all__ = [
    "StorageBackend",
    "JsonBackend",
    "PaperstoreError",
    "MissingPaperError",
    "MissingMetaError",
    "MissingSourceError",
    "MissingPaperMdError",
    "MissingMailingIndexError",
    "from_uri",
    "default_workspace_dir",
    "WORKSPACE_ENV_VAR",
]
