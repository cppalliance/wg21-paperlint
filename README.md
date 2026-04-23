# Paperlint

Paperlint finds mechanically verifiable defects in WG21 C++ standards papers — the kind of things an author would want to fix before the committee sees their work. Misspelled identifiers, broken cross-references, code samples that don't match their prose descriptions, wording that contradicts itself.

It is a linter, not a critic. It does not evaluate whether a proposal is good, whether a design is sound, or whether a paper should advance. It points at things. The committee decides the rest.

## How it works

Paperlint reads a paper, searches for defects against a rubric of 30 failure modes, then filters every candidate finding through a verification gate that rejects anything that might be intentional. What survives is a short list of items the author probably wants to know about.

The pipeline has four stages:

1. **Discovery** — reads the paper end-to-end, finds every potential defect, outputs structured findings with exact evidence quotes. By default this runs **three** LLM passes: the first pass is a full scan; each later pass is shown the findings already collected and asked to add only *additional* defects (programmatic dedup merges overlaps). Use `--discovery-passes N` on `eval` and `run` to change the count (minimum 1).
2. **Quote Verification** — programmatic check that every quoted passage actually exists in the source document. Findings with unverifiable evidence are dropped before reaching the gate.
3. **Gate** — challenges each finding, searching for reasons the author wrote it that way on purpose. Rejects aggressively. A false positive damages the credibility of every true positive around it.
4. **Evaluation** — assembles the surviving findings into a per-paper evaluation

Each stage is driven by a prompt in the `prompts/` directory. The prompts are the product. Everything else is plumbing.

For a detailed description of the pipeline architecture, models, and output schema, see [docs/design.md](paperlint/docs/design.md).

## Installation

Python 3.12 or newer is required. Paperlint bundles its PDF/HTML-to-markdown converter (`tomd`) as a sibling package in this repository; install it as an editable dependency.

```bash
git clone https://github.com/cppalliance/paperlint.git
cd paperlint
pip install -e ./tomd
pip install -e .
export OPENROUTER_API_KEY=sk-or-...   # required for eval / run (LLM stages)
```

## Quick start (third parties, wg21.org-style output)

Set a workspace directory once; all paths below are under it.

```bash
export OPENROUTER_API_KEY=sk-or-...
export WS=./data
export M=2026-02
```

**Pipeline order:** *convert* (download source → `paper.md` + `meta.json`, no LLM) → *eval* or *run* (LLM: discovery → … → `evaluation.json`). You do **not** need a separate `mailing` subcommand for normal use: `convert` / `eval` / `run` refresh the open-std [mailing index](paperlint/mailing.py) and write `mailings/<M>.json` as they start.

**What is downloaded?**

- The mailing **index** page is fetched once per command (HTML table of papers). That is *not* every PDF in the month.
- Only papers you **convert** are downloaded from their canonical URL (and cached under `.paperlint_cache/` in the CWD for `convert`).
- You never need to convert the whole mailing to evaluate one or a few papers.

**Outputs to drive your own UI** (same shapes sites like wg21.org can ingest): for each paper, `evaluation.json` (findings, references) plus `paper.md` (citations use char offsets in the JSON). After a full `run`, the workspace also has `index.json` for batch summaries.

### A. One paper (minimal)

```bash
python -m paperlint convert $M --workspace-dir "$WS" --papers P3642R4
# or: --paper P3642R4
python -m paperlint eval $M/P3642R4 --workspace-dir "$WS"
```

### B. Several papers

```bash
python -m paperlint convert $M --workspace-dir "$WS" --papers P3642R4,N5000R0
python -m paperlint run $M --workspace-dir "$WS" --papers P3642R4,N5000R0
# Or run one eval per paper: eval $M/P3642R4, eval $M/N5000R0, etc.
```

### C. Entire monthly mailing

```bash
python -m paperlint convert $M --workspace-dir "$WS" --max-cap 0 --max-workers 10
python -m paperlint run $M --workspace-dir "$WS" --max-cap 0 --max-workers 10
```

Optionally add `--max-cap N` to limit *how many* papers to process, after any `--papers` filter. Use `--max-workers` to parallelize (threads inside `convert` and `run`).

## Usage

Paperlint treats the open-std.org mailing index as authoritative for paper metadata (title, authors, audience as subgroup codes, intent info/ask, canonical URL). Every invocation names the mailing explicitly (except when using only `mailing` for index-only work).

`--workspace-dir` is the **workspace root**: the same directory is used for input and output — mailing index (`mailings/<mailing-id>.json`), per-paper trees (`paper.md`, `evaluation.json`, …), and `index.json` after a full `run`. The legacy alias `--output-dir` is accepted and means the same path.

Commands in logical order:

1. **`mailing`** (optional) — only writes `mailings/<id>.json` from open-std; no downloads of paper sources. Use when you want the index on disk before anything else.
2. **`convert`** — for each paper selected (entire list, `--papers` subset, or `--max-cap` slice), fetch and convert to `paper.md` + `meta.json`. **No** LLM, no `OPENROUTER_API_KEY` required.
3. **`eval`** (single paper) or **`run`** (batch) — load existing `paper.md` / `meta.json` and run the LLM pipeline. **Requires** prior `convert` for those papers (or you get a clear error to run `convert` first).

Fetch and persist a mailing index only (optional):

```bash
python -m paperlint mailing 2026-02 --workspace-dir ./data/
```

Convert to markdown (no AI). Examples:

```bash
# Full mailing (or use --max-cap)
python -m paperlint convert 2026-02 --workspace-dir ./data/ --max-cap 50 --max-workers 10
# One or a few paper ids (comma-separated) — does not download/convert the rest
python -m paperlint convert 2026-02 --workspace-dir ./data/ --papers P3642R4,N5000R0
python -m paperlint convert 2026-02 --workspace-dir ./data/ --paper P3642R4
```

LLM evaluation (after `convert` for the same paper(s)):

```bash
python -m paperlint eval 2026-02/P3642R4 --workspace-dir ./data/
python -m paperlint eval 2026-02/P3642R4 --workspace-dir ./data/ --discovery-passes 5
```

```bash
python -m paperlint run 2026-02 --workspace-dir ./data/ --max-cap 50 --max-workers 10
python -m paperlint run 2026-02 --workspace-dir ./data/ --papers A,B --discovery-passes 1
```

Bare paper-ids (`eval P3642R4`) and local file paths (`eval ./paper.pdf`) are not accepted — the caller must use `<mailing-id>/<paper-id>`.

### Output

Each paper produces a directory with the following files:

```
{paper_id}/
  evaluation.json   # findings, references with char offsets, metadata
  paper.md          # markdown conversion of the source paper, with YAML front matter
  meta.json         # Paper record (document_id, mailing_id, title, authors, audience, intent, …) + _runtime
```

The `extracted_char_start` and `extracted_char_end` fields in each reference select the exact evidence text in `paper.md`. This pairing is the contract for front-end citation rendering.

`paper.md` is also written by the standalone `convert` command so consumers that only need markdown ingestion can skip the AI pipeline.

For batch runs, an `index.json` summarizes the mailing with per-committee paper lists and finding counts. `mailings/<mailing-id>.json` persists the ground-truth paper index scraped from open-std.org, including the original table cells verbatim under `raw_columns`/`raw_links` so downstream consumers can read columns paperlint does not interpret.

### Storage

All on-disk writes go through `paperlint.storage.StorageBackend`; the default `JsonBackend` writes the layout above. The interface is designed so a database-backed implementation can be added without touching call sites — see [paperlint/storage.py](paperlint/storage.py).

## Environment

Paperlint requires one API key:

```bash
export OPENROUTER_API_KEY=sk-or-...
```

Or create a `.env` file in the working directory. See `.env.example`.

### Failure details and optional logging

If you run `eval` / `run` **before** `paperlint convert` for that paper, the CLI
exits with an error (missing `paper.md` / `meta.json`) and does not write
`evaluation.json` for that case.

When the **analysis** run fails, `evaluation.json` may include additive fields
`failure_stage` (typically `analysis` in that path), `failure_type`, and
`failure_message` with the exception text. Set `PAPERLINT_ERROR_TRACEBACK=1` to also
embed a `failure_traceback` string in the JSON (off by default so production
outputs stay small).

Optionally log failures to a file: set `PAPERLINT_LOG_FILE` to a path, or set
`PAPERLINT_LOG_TO_WORKSPACE=1` to append to `<workspace-dir>/paperlint.log` (the
`--workspace-dir` root must be set). Error lines are also written to **stderr** so
host tools that capture subprocess output can see them.

## What this is

A tool that reads papers and finds the kinds of errors that are easy to make and easy to miss. The same way `clang-tidy` finds a missing `const` without judging your architecture, paperlint finds a misspelled identifier without judging your proposal.

The findings are objective and mechanically verifiable. If two experts could reasonably disagree about whether something is a defect, it is not reported. The rubric defines what counts. The gate enforces it.

## What this is not

Paperlint does not speak for WG21. It is not an official tool of the committee, and its evaluations do not represent the views of any working group, study group, or individual committee member.

It does not evaluate the quality, importance, or likelihood of success of any proposal. It does not recommend for or against adoption. It does not assess design choices, alternatives, or trade-offs.

It uses AI (Claude, via the OpenRouter API) to perform the analysis. The AI reads the paper, applies the rubric, and produces structured findings. The prompts that drive the analysis are in this repository and are open for inspection.

## Repository structure

```
paperlint/
  __init__.py
  __main__.py          # CLI entry point (mailing / convert / eval / run)
  orchestrator.py      # Top-level pipeline coordination
  pipeline.py          # Discovery / verify / gate / summary steps
  llm.py               # OpenRouter client + retry/parsing helpers
  models.py            # Dataclasses (Evidence, Finding, GatedFinding, Paper, RunContext)
  extract.py           # tomd-backed paper-to-markdown wrapper + metadata fallback
  mailing.py           # WG21 open-std.org mailing page scraper
  storage.py           # StorageBackend ABC + JsonBackend
  credentials.py       # API key validation
  rubric.md            # 30 failure modes across 4 axes
  prompts/
    1-discovery.md     # "Find every defect"
    2-verification-gate.md  # "Reject everything that isn't a real defect"
    3-evaluation-writer.md  # "State what was found"
  docs/
    design.md          # Pipeline architecture and output schema
tomd/                  # Bundled PDF/HTML to markdown converter
```

## Tests

From the repository root, install the bundled converter, then paperlint with test extras (pulls in `pytest`, `mistune`, `pymupdf` for import-time dependencies):

```bash
pip install -e ./tomd
pip install -e ".[test]"
pytest tests/
```

Pytest is configured so the repo root is on `PYTHONPATH`, which lets `import tomd` resolve the vendored `tomd/` tree even before `pip install -e ./tomd`. Paperlint’s extract tests live in `tests/test_paperlint_extract.py` so a combined `pytest tests/ tomd/tests/` run does not collide with `tomd/tests/test_extract.py` on the module name `test_extract`. Running `tomd`’s own tests (`pytest tomd/tests/`) still requires `pip install -e ./tomd` (or the step above) so `mistune` and other `tomd` dependencies are present.

## License

Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)

Distributed under the Boost Software License, Version 1.0.
See [LICENSE_1_0.txt](LICENSE_1_0.txt) or http://www.boost.org/LICENSE_1_0.txt

Official repository: https://github.com/cppalliance/paperlint
