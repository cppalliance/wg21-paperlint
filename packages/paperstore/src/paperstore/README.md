# paperstore

Storage abstraction for paperflow artifacts. Every paperflow tool reads and writes through a `StorageBackend`; `JsonBackend` (filesystem-backed JSON) is the only implementation today.

## Layout

A `JsonBackend` rooted at `<workspace>` holds:

```
<workspace>/
  mailings/<mailing-id>.json        # one row per paper in the mailing
  <PAPER_ID>/
    source.pdf | source.html        # staged by mailing.download
    paper.md                        # written by tomd
    meta.json                       # written by paperlint orchestrator
    evaluation.json                 # written by paperlint pipeline
    1-findings.json, 2-gate.json, 2c-suppressed.json, ...
```

## Public surface

```python
from paperstore import (
    StorageBackend, JsonBackend, from_uri,
    PaperstoreError,
    MissingMetaError, MissingSourceError, MissingPaperMdError, MissingMailingIndexError,
)
```

Backend methods (see `StorageBackend` for the ABC):

- writes: `write_paper_md`, `write_meta_json`, `write_evaluation_json`, `write_intermediate`, `upsert_mailing_index`, `put_source`
- reads: `get_meta`, `get_source_path`, `get_paper_md`, `list_mailing`

`from_uri(uri, *, workspace_dir=None)` resolves `None`/`file://...` to a `JsonBackend`. Other schemes (e.g. `postgres://`) are reserved for future backends.

## CLI

```
python -m paperstore --workspace-dir ./scratch show-paper P3642R4
python -m paperstore --workspace-dir ./scratch list-mailings
```

## Tests

```
uv run pytest packages/paperstore/tests
```

The shared `json_store` pytest fixture (`paperstore.testing`) returns a `JsonBackend(tmp_path)`; import it for cross-package tests.
