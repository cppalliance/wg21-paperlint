#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Optional file logging for paperlint (PAPERLINT_LOG_FILE, PAPERLINT_LOG_TO_WORKSPACE)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

_LOGGER_NAME = "paperlint"
_pwl_file_handler: logging.FileHandler | None = None


def get_paperlint_logger() -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME)


def configure_paperlint_file_logging_if_needed(workspace: Path | None) -> None:
    """Add a file handler when env says so. First successful configuration wins for the process.

    * ``PAPERLINT_LOG_FILE`` — if set, log to that path.
    * Else, if ``PAPERLINT_LOG_TO_WORKSPACE`` is truthy and *workspace* is set, use
      ``<workspace>/paperlint.log``.
    """
    global _pwl_file_handler
    if _pwl_file_handler is not None:
        return
    path: str | None = None
    raw = os.environ.get("PAPERLINT_LOG_FILE", "").strip()
    if raw:
        path = raw
    elif workspace and os.environ.get("PAPERLINT_LOG_TO_WORKSPACE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        path = str(Path(workspace) / "paperlint.log")
    if not path:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    h = logging.FileHandler(p, encoding="utf-8")
    h.setLevel(logging.DEBUG)
    h.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [paperlint] %(message)s")
    )
    _pwl_file_handler = h
    log = get_paperlint_logger()
    log.setLevel(logging.DEBUG)
    log.addHandler(h)
