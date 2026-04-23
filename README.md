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
```

## Usage

Paperlint treats the open-std.org mailing index as authoritative for paper metadata (title, authors, audience, paper_type, canonical URL). Every invocation names the mailing explicitly.

`--workspace-dir` is the **workspace root**: the same directory is used for input and output — mailing index (`mailings/<mailing-id>.json`), per-paper trees (`paper.md`, `evaluation.json`, …), and `index.json` after a full `run`. The legacy alias `--output-dir` is accepted and means the same path.

Fetch and persist a mailing index (ground-truth paper metadata from open-std.org):

```bash
python -m paperlint mailing 2026-02 --workspace-dir ./data/
```

Convert all papers in a mailing to markdown — no AI evaluation:

```bash
python -m paperlint convert 2026-02 --workspace-dir ./data/ --max-cap 50 --max-workers 10
```

Evaluate a single paper (mailing-id + paper-id):

```bash
python -m paperlint eval 2026-02/P3642R4 --workspace-dir ./data/
python -m paperlint eval 2026-02/P3642R4 --workspace-dir ./data/ --discovery-passes 5
```

Evaluate every paper in a mailing (full pipeline, AI included):

```bash
python -m paperlint run 2026-02 --workspace-dir ./data/ --max-cap 50 --max-workers 10
python -m paperlint run 2026-02 --workspace-dir ./data/ --discovery-passes 1
```

Bare paper-ids (`eval P3642R4`) and local file paths (`eval ./paper.pdf`) are not accepted — the caller must name the mailing.

### Output

Each paper produces a directory with the following files:

```
{paper_id}/
  evaluation.json   # findings, references with char offsets, metadata
  paper.md          # markdown conversion of the source paper, with YAML front matter
  meta.json         # PaperMeta record (title, authors, audience, paper_type, ...)
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
  models.py            # Dataclasses (Evidence, Finding, GatedFinding, PaperMeta)
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
