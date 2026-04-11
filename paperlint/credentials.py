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
    """Load .env files from CWD upward, with .env.local overriding."""
    load_dotenv(find_dotenv(".env"), encoding="utf-8-sig")
    load_dotenv(find_dotenv(".env.local"), override=True, encoding="utf-8-sig")


def _env_nonempty(name: str) -> bool:
    v = os.environ.get(name)
    if v is None:
        return False
    return bool(str(v).strip())


def resolve_openrouter_base_url() -> str:
    """Return OPENROUTER_BASE_URL from environment, or the default."""
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


def ensure_api_keys(*, all_openrouter: bool) -> None:
    """Validate required API keys before the pipeline runs.

    Default (mixed) pipeline: requires ANTHROPIC_API_KEY and OPENROUTER_API_KEY.
    --all-openrouter: requires OPENROUTER_API_KEY only.
    """
    _load_env()
    if all_openrouter:
        if not _env_nonempty("OPENROUTER_API_KEY"):
            raise ValueError(
                "paperlint --all-openrouter requires OPENROUTER_API_KEY in the "
                "environment or .env / .env.local."
            )
        resolve_openrouter_base_url()
        return

    if not _env_nonempty("ANTHROPIC_API_KEY"):
        raise ValueError(
            "paperlint requires ANTHROPIC_API_KEY for Anthropic API steps "
            "(or use --all-openrouter). Set it in the environment or .env / .env.local."
        )
    if not _env_nonempty("OPENROUTER_API_KEY"):
        raise ValueError(
            "paperlint requires OPENROUTER_API_KEY for OpenRouter steps. "
            "Set it in the environment or .env / .env.local."
        )
    resolve_openrouter_base_url()
