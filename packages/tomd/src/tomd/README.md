# tomd

Convert WG21 committee papers from PDF or HTML to clean Markdown.

tomd is purpose-built for C++ standards committee paper conversion. It
understands WG21 metadata fields (document number, date, reply-to, audience),
detects structural elements (headings, lists, tables, code blocks, wording
sections), and produces Markdown that looks like a human wrote it, suitable
for version control, pull request diffs, and plain-text review workflows.

## Install

From this directory:

```
pip install -e .
```

Requires Python 3.12 or newer. Runtime dependencies (`pymupdf~=1.27`,
`beautifulsoup4~=4.14`, `mistune~=3.2`) are declared in `pyproject.toml`
and installed automatically.

## Usage

tomd reads sources staged in a paperstore workspace (run `python -m mailing` first):

```
python -m tomd P3642R4 --workspace-dir ./data            # one paper
python -m tomd P3642R4 P3700R0 --workspace-dir ./data    # multiple
python -m tomd 2026-04 --workspace-dir ./data            # every paper in mailing 2026-04
python -m tomd 2026-04 P3700R0 --workspace-dir ./data    # mix mailing + paper ids
python -m tomd 2026-04 --workspace-dir ./data --qa       # batch QA scoring
python -m tomd 2026-04 --workspace-dir ./data -v         # verbose logging
```

Mailing-id positionals (matching `YYYY-MM`) expand to every paper id in that mailing's index, in stored order. The mailing index must already exist on disk - run `python -m mailing <id> --workspace-dir DIR` first, otherwise tomd raises `MissingMailingIndexError`.

The pre-0.2 file-path interface (`tomd input.pdf`) was removed.

### QA mode

Score conversion quality across a batch of PDFs without inspecting each
output by hand:

```
tomd --qa *.pdf *.html                         # ranked report to stdout
tomd --qa --workers 16 *.pdf *.html            # parallel (16 processes)
tomd --qa --qa-json report.json *.pdf *.html   # + detailed per-file JSON
tomd --qa --workers 16 --timeout 180 *.pdf     # abort stragglers after 3m
```

Each file is converted and then scored by parsing the Markdown output with
mistune. The score (0-100) reflects heading structure, code block detection,
front-matter completeness, uncertain regions, and unfenced code.

### Output

- `paper.md` is always produced. It contains YAML front matter (title,
  document number, date, audience, reply-to) followed by the paper body
  rendered as Markdown.
- `paper.prompts.md` is produced only when the converter found uncertain
  regions. It pairs each uncertain span with both extraction paths (MuPDF
  and spatial) plus surrounding context, formatted for manual LLM
  reconciliation. If no uncertain regions exist, no prompts file is written
  (and any stale one at the output path is removed).

### Uncertain regions

tomd uses dual-extraction with confidence scoring. When the MuPDF and
spatial paths disagree on a page, the region is emitted in the output
marked with an HTML comment:

```
<!-- tomd:uncertain:L120-L145 -->
```

The accompanying `.prompts.md` file contains ready-to-feed LLM prompts for
each marker. You resolve uncertain regions manually; the LLM fixes
structure, never content.

## Limitations

- **No OCR.** Scanned or image-only PDFs are not supported.
- **No vision fallback.** Papers that rely on non-extractable layout
  (complex equations, diagrams) will not convert cleanly.
- **HTML generator coverage.** Five generators are detected directly:
  mpark/wg21, Bikeshed, HackMD, wg21 cow-tool, and hand-written. Other
  sources fall back to a generic extractor that may miss metadata fields.
- **LLM auto-resolution is deferred to v2.** The `.prompts.md` file is
  produced; feeding it to an LLM and applying the result is manual in this
  release.
- **Slide decks are detected and skipped.** Presentation-style PDFs
  (landscape pages smaller than standard paper) produce an empty `.md`
  and a `.prompts.md` noting the slide-deck detection.
- **Standards drafts (>= 200 pages) are detected and skipped.** These are
  C++ standard documents, not technical papers. They produce an empty `.md`
  and a `.prompts.md` noting the detection.

## Design

Design and architecture documentation lives alongside the code:

- [`CLAUDE.md`](CLAUDE.md) - architecture rules and invariants (contributors
  and AI agents).
- [`lib/pdf/ARCHITECTURE.md`](lib/pdf/ARCHITECTURE.md) - PDF converter
  pipeline and the techniques it uses.
- [`lib/html/ARCHITECTURE.md`](lib/html/ARCHITECTURE.md) - HTML converter
  pipeline.

Read these in order if you are modifying tomd.

## Development

Install test extras and run the suite:

```
pip install -e .[test]
pytest tests/
```

## License

Boost Software License 1.0. See [`LICENSE`](LICENSE).
