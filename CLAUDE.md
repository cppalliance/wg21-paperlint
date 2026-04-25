# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## Project context

Paperflow is the uv-workspace monorepo for **PaperLint** and the three libraries it depends on. PaperLint is one project in a wider C++ Alliance / WG21 initiative that Vinnie Falco calls **Civilization Level Reform (CLR)**: an umbrella covering Agora21 (AI red-team analysis of WG21 papers), PRAGMA (the SD-1 voting booth), C++ Herald (AI-generated political journalism), and PaperLint (this repo, objective paper evaluation).

PaperLint is **Sergio DuBois's** project; the bundled `tomd` converter was absorbed from the now-retired [cppalliance/tomd](https://github.com/cppalliance/tomd) (originally Greg Kaleka's) and is now first-class in `packages/tomd/`. For the full glossary of people, related projects, and naming conventions (Agora21, PRAGMA, themod, paperflow, NeuronsLab, ...), the authoritative reference is [`../civ-lvl-rfrm/CLAUDE.md`](../civ-lvl-rfrm/CLAUDE.md) and the PDFs under `../civ-lvl-rfrm/context/`. Do not duplicate that glossary here; link to it when ambiguity shows up.

Practical consequences:

- Canonical spellings: **PaperLint** (in prose) and **paperlint** (package / CLI), **tomd** (lowercase always, commonly misheard as "2MD"), **WG21** (no space), **Scrivener** / **Paperworks** for the other Alliance tools, **paperflow** (system + repo).
- April 2026 mailing (`2026-04`) is the realistic exercising corpus until May.

## Repository layout

uv workspace with one root `pyproject.toml` and four members under `packages/`:

```
wg21-paperflow/
  pyproject.toml            # workspace root
  uv.lock
  packages/
    paperstore/             # storage abstraction (JsonBackend today)
    mailing/                # scrape + download from open-std.org
    tomd/                   # PDF / HTML to Markdown
    paperlint/              # LLM defect-finder pipeline (user-facing CLI)
  tests/                    # one cross-package integration test
```

Per-package agent rules live in `packages/<name>/src/<name>/CLAUDE.md` and own the deep guidance for their package. This file is the umbrella; consult the per-package files when working inside one.

## Environment

Python 3.12+. There is no lockfile beyond `uv.lock`. Development install:

```bash
uv sync                                   # installs all four packages + dev deps
export OPENROUTER_API_KEY=sk-or-...       # .env / .env.local also auto-loaded
```

`mistune`, `pymupdf`, and `beautifulsoup4` are runtime deps of `tomd` (not test-only) because `paperlint`'s convert path imports `tomd` at module-load time.

## Running the CLI

Two-step flow:

1. **`paperlint convert <mailing-id>`** - fetch sources and write `paper.md` + `meta.json`. No LLM, no API key needed.
2. **`paperlint eval <mailing-id>/<paper-id>`** (single) or **`paperlint run <mailing-id>`** (batch) - load the converted artifacts and run the LLM pipeline. Missing `paper.md` / `meta.json` is a hard error: the CLI tells the caller to run `convert` first and exits.

Bare paper ids (`eval P3642R4`) and local file paths are not accepted; every invocation names the mailing explicitly. The open-std.org mailing index is authoritative for title / authors / audience / paper_type and is refetched on every `convert` / `eval` / `run` (index only; not the PDFs).

`--workspace-dir` (alias `--output-dir`) is both the input and output root for the default `JsonBackend`. `--papers A,B` / `--paper X` filter the mailing list, then `--max-cap N` slices, then `--max-workers N` parallelizes. `--discovery-passes N` (default 3) controls the multi-pass discovery stage.

Per-package CLIs (`python -m paperstore`, `python -m mailing ...`, `python -m tomd ...`) are also installed.

## Running tests

```bash
uv run pytest                                  # full workspace
uv run --package paperstore pytest             # one package in isolation
uv run pytest tests/test_end_to_end_convert.py # the cross-package integration
```

Tests are hermetic by design. None of the LLM calls are hit in-process; the pipeline modules are stubbed at the seam (`paperlint.llm.call_with_retry`, `build_client`). `requests.get` in `mailing.download` is the stub seam for download tests.

## Pipeline architecture (one-paragraph summary)

`run_paper_eval` (`packages/paperlint/src/paperlint/orchestrator.py`) orchestrates per-paper evaluation: load the previously-converted paper, run multi-pass LLM discovery, drop findings whose evidence quotes don't appear in `paper.md`, run the LLM gate, suppress known false positives, write the prose summary, assemble `evaluation.json`. Detailed step list and invariants live in [`packages/paperlint/src/paperlint/CLAUDE.md`](packages/paperlint/src/paperlint/CLAUDE.md).

## Workspace-wide invariants

- **Storage goes through `paperstore.StorageBackend`.** `JsonBackend` is the only implementation, but call sites must not assume it. A future Postgres backend will drop in without code changes elsewhere. Don't bypass the backend by writing files directly from orchestrator or pipeline.
- **`convert` and `eval`/`run` never share work.** Eval reads `paper.md` and `meta.json` via the backend; it never refetches or re-tomds. If you find yourself adding a fetch to the eval path, reconsider.
- **`prompt_hash`** is a SHA-256 (truncated to 12 hex chars) over all `packages/paperlint/src/paperlint/prompts/**/*.md` plus `rubric.md`, sorted lexically. Any prompt or rubric edit flips the hash; consumers should treat prior runs as stale. Extensions in `paperlint/prompts/extensions/` are hashed even though they are not yet wired into a pipeline step.
- **Always write `evaluation.json`, even on analysis failure.** The orchestrator catches analysis-stage exceptions and writes a `pipeline_status="partial"` skeleton. Missing `paper.md` / `meta.json` is a different path: it raises `FileNotFoundError` and writes nothing.

## Failure model and logging

- `PAPERLINT_ERROR_TRACEBACK=1` - embed tracebacks in `evaluation.json` on partial runs.
- `PAPERLINT_LOG_FILE=/path/to/log` - append structured logs there.
- `PAPERLINT_LOG_TO_WORKSPACE=1` - append to `<workspace>/paperlint.log` instead.

`paperlint.logutil` owns log configuration and is idempotent.

## Writing style

- Do not use em dashes (`--`) in prose, commit messages, or PR bodies. Use commas, periods, or colons.
- Copyright headers on new `.py` files follow Boost Software License 1.0. Attribute the file to whoever authors it (the contributor directing the work), not to a fixed project-wide name. When editing an existing file, leave the original author's header alone.
