# paperlint

The LLM pipeline that finds mechanically verifiable defects in WG21 C++ standards papers. Misspelled identifiers, broken cross-references, code samples that don't match their prose, contradictions. PaperLint points at things; the committee decides the rest.

## Two-step flow

Conversion is separated from evaluation so eval/run never duplicate fetch + tomd work.

```bash
# 1) Convert: fetch sources, build paper.md + meta.json. No LLM, no API key.
python -m paperlint convert 2026-04 --workspace-dir ./data --paper P3642R4

# 2) Evaluate: load the converted artifacts, run the LLM pipeline.
export OPENROUTER_API_KEY=sk-or-...
python -m paperlint eval 2026-04/P3642R4 --workspace-dir ./data
```

`run` is the batch form of `eval`. Bare paper ids (`eval P3642R4`) and local file paths are not accepted; every invocation names the mailing explicitly so the open-std.org index stays authoritative.

## CLI

| Subcommand | Purpose |
|---|---|
| `mailing` | Fetch and persist `mailings/<id>.json` |
| `convert` | Fetch + tomd; writes `paper.md` + `meta.json` per paper |
| `eval`    | Run the LLM pipeline on one converted paper |
| `run`     | Batch `eval` over a mailing |

`--workspace-dir` (alias `--output-dir`) is both input and output for the JSON storage backend. `--papers A,B`, `--paper X`, `--max-cap`, and `--max-workers` filter and parallelize. `--discovery-passes` (default 3) controls the multi-pass discovery stage.

## Models

Pinned in `paperlint/llm.py`:

- Discovery + Gate: `anthropic/claude-opus-4.6`, JSON mode, extended thinking enabled.
- Summary: `anthropic/claude-sonnet-4.6`, JSON mode, no thinking.

Routing is OpenRouter via the `openai` SDK.

## Environment

- `OPENROUTER_API_KEY` (required for `eval` / `run`; loaded from `.env` / `.env.local` automatically).
- `PAPERLINT_LOG_FILE=/path/to/log` - append structured logs there.
- `PAPERLINT_LOG_TO_WORKSPACE=1` - append to `<workspace>/paperlint.log` instead.
- `PAPERLINT_ERROR_TRACEBACK=1` - embed tracebacks in `evaluation.json` on partial runs.

## Tests

```
uv run pytest packages/paperlint/tests
```

Tests are hermetic: LLM calls are stubbed at `paperlint.llm.call_with_retry` / `build_client`. Don't add tests that hit OpenRouter.
