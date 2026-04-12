#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""API key validation and OpenRouter base URL resolution."""

from __future__ import annotations

import os

from dotenv import load_dotenv, find_dotenv

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _load_env() -> None:
    load_dotenv(find_dotenv(".env"), encoding="utf-8-sig")
    load_dotenv(find_dotenv(".env.local"), override=True, encoding="utf-8-sig")


def resolve_openrouter_base_url() -> str:
    raw = os.environ.get("OPENROUTER_BASE_URL")
    if raw is None:
        return DEFAULT_OPENROUTER_BASE_URL
    stripped = str(raw).strip()
    if not stripped:
        raise ValueError(
            "OPENROUTER_BASE_URL is set but empty. Unset it to use the default "
            f"({DEFAULT_OPENROUTER_BASE_URL}) or set a non-empty URL."
        )
    return stripped


def ensure_api_keys() -> None:
    """Validate required API key before the pipeline runs."""
    _load_env()
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "paperlint requires OPENROUTER_API_KEY. "
            "Set it in the environment or .env / .env.local."
        )
    resolve_openrouter_base_url()
