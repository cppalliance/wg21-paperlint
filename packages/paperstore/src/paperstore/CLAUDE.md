# paperstore - Agent Rules

## What this is

The storage abstraction for paperflow. Every other package depends on paperstore; paperstore depends only on the standard library. Adding cross-package imports here is a layering violation.

## Invariants

- **`JsonBackend` is currently the only backend.** A Postgres backend is planned but deferred. New methods must be added to the `StorageBackend` ABC first; do not let `JsonBackend`-specific behavior leak into call sites.
- **`get_source_path -> Path` assumes a local filesystem.** Non-local backends must materialize bytes to a temp file before returning. Document this in any new backend.
- **`get_meta` falls back to the mailing-index row** when `meta.json` is absent. This is intentional: tomd runs after mailing but before paperlint writes `meta.json`, and it needs paper-type/title from the mailing row to fill YAML fallback. Don't remove the fallback without tracing every caller.
- **Errors are typed.** Raise `MissingSourceError` / `MissingMetaError` / `MissingPaperMdError` / `MissingMailingIndexError` (all subclasses of `PaperstoreError`), not generic `FileNotFoundError`, so callers can distinguish stages.
- **`mailings/` is the only top-level workspace dir not named after a paper id.** Don't introduce more sibling dirs without updating consumers that scan the workspace.

## When to bypass

Don't. Every CLI in the workspace uses `JsonBackend` (or `from_uri`); writing files directly would defeat the abstraction.
