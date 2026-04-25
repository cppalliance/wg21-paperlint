# paperflow

Paperflow is a uv-managed monorepo of four cooperating packages that fetch, convert, and lint WG21 C++ standards papers. It is part of the wider C++ Alliance / WG21 Civilization Level Reform initiative; PaperLint is the user-facing tool, and the other three packages are the seams underneath it.

## Packages

| Package | Purpose |
|---|---|
| [`paperstore`](packages/paperstore/src/paperstore/README.md) | Storage abstraction. JsonBackend today; Postgres later, without touching call sites. |
| [`mailing`](packages/mailing/src/mailing/README.md) | Scrape the open-std.org mailing index; download paper sources into the store. |
| [`tomd`](packages/tomd/src/tomd/README.md) | PDF / HTML to clean Markdown for committee papers. |
| [`paperlint`](packages/paperlint/src/paperlint/README.md) | The LLM defect-finder pipeline. The user-facing CLI. |

Dependency graph (all libraries; no circular deps):

```
paperstore                        (stdlib only)
mailing      -> paperstore        (download writes via put_source)
tomd         -> paperstore        (reads source + meta, writes paper.md)
paperlint    -> paperstore, mailing, tomd
```

## Install

Python 3.12 or newer. uv replaces the old `pip install -e ".[test]"` flow:

```bash
git clone https://github.com/cppalliance/paperlint.git wg21-paperflow
cd wg21-paperflow
uv sync                           # installs all four packages + dev deps
export OPENROUTER_API_KEY=sk-or-...  # required for paperlint eval / run
```

`.env` and `.env.local` are auto-loaded.

## Two-step flow

Conversion is separated from evaluation so eval/run never duplicate work.

```bash
# 1) Convert a paper (no LLM, no API key).
uv run python -m paperlint convert 2026-04 --workspace-dir ./data --paper P3642R4

# 2) Evaluate the converted paper.
uv run python -m paperlint eval 2026-04/P3642R4 --workspace-dir ./data
```

The open-std.org mailing index is authoritative for paper metadata and is refetched on every command. Bare paper ids and local file paths are not accepted.

## Per-package CLIs

Each package ships its own CLI for direct use; the natural flow without paperlint is `mailing` then `tomd`:

```bash
# Fetch index + download every paper's source. Idempotent: re-running with
# no new papers is a no-op for the network.
uv run python -m mailing 2026-04 --workspace-dir ./data

# Convert every paper in the mailing to markdown (mailing-id expands).
uv run python -m tomd 2026-04 --workspace-dir ./data

# Score conversion quality across the corpus.
uv run python -m tomd 2026-04 --workspace-dir ./data --qa --qa-json ./data/qa.json

# Inspect what's stored.
uv run python -m paperstore --workspace-dir ./data list-mailings
uv run python -m paperstore --workspace-dir ./data show-paper P3642R4
```

Single-paper variants are still available (`python -m mailing 2026-04/P3642R4`, `python -m tomd P3642R4`).

## Tests

```bash
uv run pytest                                # full workspace (~545 tests + 1 integration)
uv run --package paperstore pytest           # one package in isolation
uv run --package mailing pytest
uv run --package tomd pytest
uv run --package paperlint pytest
```

The cross-package integration test (`tests/test_end_to_end_convert.py`) drives `mailing.download` -> `tomd.api.convert_paper` against a stubbed `requests.get`.

## Layout

```
wg21-paperflow/
  pyproject.toml          # workspace root
  uv.lock
  packages/
    paperstore/
    mailing/
    tomd/
    paperlint/
  tests/                  # one cross-package integration test
```

## License

Boost Software License 1.0. See `LICENSE_1_0.txt`.
