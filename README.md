# Paperlint

Paperlint finds mechanically verifiable defects in WG21 C++ standards papers — the kind of things an author would want to fix before the committee sees their work. Misspelled identifiers, broken cross-references, code samples that don't match their prose descriptions, wording that contradicts itself.

It is a linter, not a critic. It does not evaluate whether a proposal is good, whether a design is sound, or whether a paper should advance. It points at things. The committee decides the rest.

## How it works

Paperlint reads a paper, searches for defects against a rubric of 30 failure modes, then filters every candidate finding through a verification gate that rejects anything that might be intentional. What survives is a short list of items the author probably wants to know about.

The pipeline has four stages:

1. **Discovery** — reads the paper end-to-end, finds every potential defect, outputs structured findings with exact evidence quotes
2. **Quote Verification** — programmatic check that every quoted passage actually exists in the source document. Findings with unverifiable evidence are dropped before reaching the gate.
3. **Gate** — challenges each finding, searching for reasons the author wrote it that way on purpose. Rejects aggressively. A false positive damages the credibility of every true positive around it.
4. **Evaluation** — assembles the surviving findings into a per-paper evaluation

Each stage is driven by a prompt in the `prompts/` directory. The prompts are the product. Everything else is plumbing.

For a detailed description of the pipeline architecture, models, and output schema, see [docs/design.md](paperlint/docs/design.md).

## Installation

```bash
git clone https://github.com/cppalliance/paperlint.git
cd paperlint
pip install -e .
```

## Usage

Paperlint treats the open-std.org mailing index as authoritative for paper metadata (title, authors, audience, paper_type, canonical URL). Every invocation names the mailing explicitly.

Evaluate a single paper (mailing-id + paper-id):

```bash
python -m paperlint eval 2026-02/P3642R4 --output-dir ./output/
```

Evaluate an entire mailing:

```bash
python -m paperlint run 2026-02 --output-dir ./data/ --max-cap 50 --max-workers 10
```

Fetch and persist a mailing index (ground-truth paper metadata from open-std.org):

```bash
python -m paperlint mailing 2026-02
```

Bare paper-ids (`eval P3642R4`) and local file paths (`eval ./paper.pdf`) are not accepted — the caller must name the mailing.

### Output

Each paper produces a directory with two files:

```
{paper_id}/
  evaluation.json   # findings, references with char offsets, metadata
  paper.md          # canonical markdown extraction of the source paper
```

The `extracted_char_start` and `extracted_char_end` fields in each reference select the exact evidence text in `paper.md`. This pairing is the contract for front-end citation rendering.

For batch runs, an `index.json` summarizes the mailing with per-committee paper lists and finding counts. A `mailings/{mailing_id}.json` persists the ground-truth paper index scraped from open-std.org.

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
  __main__.py          # CLI entry point
  orchestrator.py      # Pipeline implementation
  credentials.py       # API key validation
  extract.py           # HTML/PDF text extraction
  mailing.py           # WG21 mailing page scraper
  rubric.md            # 30 failure modes across 4 axes
  prompts/
    1-discovery.md     # "Find every defect"
    2-verification-gate.md  # "Reject everything that isn't a real defect"
    3-evaluation-writer.md  # "State what was found"
  docs/
    design.md          # Pipeline architecture and output schema
```

## License

Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)

Distributed under the Boost Software License, Version 1.0.
See [LICENSE_1_0.txt](LICENSE_1_0.txt) or http://www.boost.org/LICENSE_1_0.txt

Official repository: https://github.com/cppalliance/paperlint
