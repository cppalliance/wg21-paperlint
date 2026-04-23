#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""OpenRouter (OpenAI-compatible) client and LLM call helpers."""

from __future__ import annotations

import json
import os
import sys
import time

import openai

from paperlint.credentials import resolve_openrouter_base_url

OPENROUTER_MODEL = "anthropic/claude-opus-4.6"
OPENROUTER_SONNET = "anthropic/claude-sonnet-4.6"

THINKING_BUDGET = {
    "discovery": 128_000,
    "gate": 128_000,
    "summary": 8_000,
}

MAX_TOKENS = {
    "discovery": 128_000,
    "gate": 128_000,
    "summary": 4_096,
}

MAX_RETRIES = 3
RETRY_BASE_DELAY = 10


def build_client() -> openai.OpenAI:
    """Construct an OpenAI SDK client pointed at OpenRouter."""
    return openai.OpenAI(
        base_url=resolve_openrouter_base_url(),
        api_key=os.environ["OPENROUTER_API_KEY"],
    )


def log_error(step: str, exc: BaseException, *, model: object = None) -> None:
    lines = [f"paperlint [{step}] API error: {type(exc).__name__}: {exc}"]
    if model is not None:
        lines.append(f"paperlint [{step}] model: {model}")
    code = getattr(exc, "status_code", None)
    if code is not None:
        lines.append(f"paperlint [{step}] HTTP status: {code}")
    body = getattr(exc, "body", None)
    if isinstance(body, str) and body.strip():
        b = body.strip()[:2000]
        lines.append(f"paperlint [{step}] error body: {b}")
    for line in lines:
        print(line, file=sys.stderr)


def call_with_retry(client: openai.OpenAI, step: str, **kwargs):
    model = kwargs.get("model", "?")
    for attempt in range(MAX_RETRIES):
        try:
            return client.chat.completions.create(**kwargs)
        except (openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError) as e:
            if attempt == MAX_RETRIES - 1:
                log_error(step, e, model=model)
                raise
            wait = RETRY_BASE_DELAY * (attempt + 1)
            label = type(e).__name__
            print(f"  [{step}] {label}. Waiting {wait}s ({attempt + 1}/{MAX_RETRIES})...")
            time.sleep(wait)
        except Exception as e:
            log_error(step, e, model=model)
            raise


def log_usage(step: str, response, budget: int) -> None:
    u = response.usage
    prompt_tok = u.prompt_tokens if u else 0
    completion_tok = u.completion_tokens if u else 0
    total_tok = u.total_tokens if u else 0
    print(
        f"\n  [{step}] tokens — prompt: {prompt_tok} | completion: {completion_tok} "
        f"| total: {total_tok} | thinking_budget: {budget}"
    )


def extract_response_text(response) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""
    msg = choices[0].message
    return msg.content if msg and msg.content else ""


def strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw[raw.index("\n") + 1:] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[: raw.rfind("```")].strip()
    return raw


def parse_json(raw: str, step: str = "") -> dict | list:
    stripped = strip_fences(raw)
    decoder = json.JSONDecoder()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    if start >= 0:
        try:
            result, _ = decoder.raw_decode(stripped, start)
            return result
        except json.JSONDecodeError:
            pass

    try:
        result, _ = decoder.raw_decode(stripped)
        return result
    except json.JSONDecodeError as e:
        label = step or "JSON"
        print(f"paperlint [{label}] JSONDecodeError: {e}", file=sys.stderr)
        preview = stripped[:800]
        print(f"paperlint [{label}] raw: {repr(preview)}", file=sys.stderr)
        raise
